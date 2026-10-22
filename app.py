"""Run: streamlit run app.py"""
from __future__ import annotations
import io
import zipfile
from pathlib import Path
import pandas as pd
import streamlit as st
from analyzer import analyze, to_excel

st.set_page_config(page_title='Spalding Course Requirement Analyzer',page_icon='📚',layout='wide')
st.title('Spalding Course Requirement Analyzer')
st.write('See which program sheets list each course, with named programs and counts.')
st.caption('Counts program-sheet listings, Always review extracted results.')

@st.cache_data
def catalog():
    return pd.read_csv(Path(__file__).with_name('course_catalog.csv')).fillna('')

pdfs=st.file_uploader('Upload undergraduate program sheet PDFs',type=['pdf'],accept_multiple_files=True)
archive=st.file_uploader('Or upload a ZIP of program-sheet PDFs',type=['zip'])
all_files=[]
for upload in pdfs or []:
    all_files.append((upload.name,upload.getvalue()))
if archive:
    try:
        with zipfile.ZipFile(io.BytesIO(archive.getvalue())) as z:
            for entry in z.infolist():
                if entry.is_dir() or not entry.filename.lower().endswith('.pdf'):
                    continue
                if entry.file_size>20_000_000:
                    st.warning(f'Skipped large file: {entry.filename}')
                    continue
                all_files.append((Path(entry.filename).name,z.read(entry)))
    except Exception as ex:
        st.error(f'Could not open ZIP: {ex}')

if all_files:
    if len(all_files)>200:
        st.error('Upload at most 200 PDFs in one analysis.')
        st.stop()
    st.write(f'**{len(all_files)} PDFs ready**')
    if st.button('Analyze program sheets',type='primary'):
        with st.spinner('Extracting courses and matching Jane’s catalog...'):
            summary,detail,subjects,audit=analyze(all_files,catalog())
        st.session_state['analysis']=(summary,detail,subjects,audit)

if 'analysis' in st.session_state:
    summary,detail,subjects,audit=st.session_state['analysis']
    a,b,c=st.columns(3)
    a.metric('Program sheets',len(audit))
    b.metric('Numbered courses and subject requirements',len(summary))
    c.metric('Numbered course-program listings',len(detail))
    st.subheader('Find a course')
    query=st.text_input('Search course number, title, or program name',placeholder='ECON 281, Accounting, History...').strip()
    results=summary.copy()
    if query:
        mask=results.astype(str).apply(lambda column:column.str.contains(query,case=False,regex=False)).any(axis=1)
        results=results[mask]
    if not subjects.empty:
        extras=[]
        for subject,group in subjects.groupby('Subject'):
            programs=sorted(set(group['Program sheet']))
            extras.append({'Course code':subject,'Catalog title':'Unspecified '+subject+' course','Number of program sheets':len(programs),'Program sheets':'; '.join(programs),'Jane catalog match':'Subject-only requirement'})
        results=pd.concat([results,pd.DataFrame(extras)],ignore_index=True)
        if query:
            results=results[results.astype(str).apply(lambda col:col.str.contains(query,case=False,regex=False)).any(axis=1)]
    results=results.sort_values(['Number of program sheets','Course code'],ascending=[False,True])
    st.dataframe(results,hide_index=True,use_container_width=True)
    with st.expander('See which programs list each course or subject requirement'):
        st.dataframe(detail,hide_index=True,use_container_width=True)
        if not subjects.empty:
            st.dataframe(subjects,hide_index=True,use_container_width=True)
    failed=audit[audit['Status']!='Extracted']
    if not failed.empty:
        st.warning(f"{len(failed)} PDF(s) may need review because extraction found no numbered courses or encountered an error.")
        st.dataframe(failed,hide_index=True,use_container_width=True)
    st.caption('Course codes not found in Jane’s catalog are flagged as Review in Courses by Program. Subject-only requirements like HIST and RS are counted separately from specific courses.')
    st.warning('These counts represent program sheets, not confirmed enrollment demand or unique degree programs. A listed course may be optional or mentioned in a note.')
    subject_counts=[]
    if not subjects.empty:
        for subject,group in subjects.groupby('Subject'):
            programs=sorted(set(group['Program sheet']))
            subject_counts.append({'Course code':subject,'Catalog title':'Unspecified '+subject+' course','Number of program sheets':len(programs),
                                   'Program sheets':'; '.join(programs),'Jane catalog match':'Subject-only requirement'})
    combined_summary=pd.concat([summary,pd.DataFrame(subject_counts)],ignore_index=True).sort_values(['Number of program sheets','Course code'],ascending=[False,True]).reset_index(drop=True)
    subject_detail=pd.DataFrame([
        {'Program sheet':r['Program sheet'],'Course code':r['Subject'],
         'Catalog title':'Unspecified '+r['Subject']+' course','In Jane catalog':'Subject-only requirement','Pages':str(r['Page'])}
        for _,r in subjects.iterrows()
    ],columns=detail.columns)
    combined_detail=pd.concat([detail,subject_detail],ignore_index=True).drop_duplicates(subset=['Program sheet','Course code']).sort_values(['Program sheet','Course code']).reset_index(drop=True)
    report=to_excel([('Course Counts',combined_summary),('Courses by Program',combined_detail)])
    st.download_button('Download Excel analysis',data=report,file_name='spalding_course_requirements.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',type='primary')
