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
st.write('See which program sheets list each course, with named programs and counts. No database required.')
st.caption('Counts program-sheet listings, not students or projected enrollment. Always review extracted results.')

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
    b.metric('Distinct numbered courses',len(summary))
    c.metric('Course-program listings',len(detail))
    st.subheader('Find a course')
    query=st.text_input('Search course number, title, or program name',placeholder='ECON 281, Accounting, History...').strip()
    results=summary.copy()
    if query:
        mask=results.astype(str).apply(lambda column:column.str.contains(query,case=False,regex=False)).any(axis=1)
        results=results[mask]
    st.dataframe(results,hide_index=True,use_container_width=True)
    with st.expander('Each program-course listing'):
        st.dataframe(detail,hide_index=True,use_container_width=True)
    with st.expander('Subject-only / unspecified requirements (HIST, RS, etc.)'):
        st.dataframe(subjects,hide_index=True,use_container_width=True)
    with st.expander('Extraction audit and missing course matches'):
        st.dataframe(audit,hide_index=True,use_container_width=True)
        st.dataframe(detail[detail['In Jane catalog']=='Review'],hide_index=True,use_container_width=True)
    st.warning('A course code appearing on a sheet does not prove it is mandatory: alternatives, notes, and double-major sheets require human review. Multiple sheets may represent overlapping student populations.')
    report=to_excel([('Course Counts',summary),('Course by Program',detail),('Subject Requirements',subjects),('Extraction Audit',audit),('Unmatched Codes',detail[detail['In Jane catalog']=='Review'])])
    st.download_button('Download Excel analysis',data=report,file_name='spalding_course_requirements.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',type='primary')
