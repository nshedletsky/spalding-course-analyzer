"""Curriculum PDF inventory: counts occurrences on sheets, not enrollment demand."""
from __future__ import annotations
import re
from io import BytesIO
from collections import defaultdict
import fitz
import pandas as pd

COURSE_PATTERN = re.compile(r'(?<![A-Za-z0-9])([A-Z]{2,6})\s*[-– ]\s*(\d{3}[A-Z]?)(?!\w)')
SUBJECT_PATTERN = re.compile(r'(?<![A-Z0-9])(?:_+\s*)?([A-Z]{2,6})\s*_+(?!\w)|^\s*([A-Z]{2,6})\s*(?:[1-9]|1[0-2])?\s*$')


def normalize_code(code):
    match=COURSE_PATTERN.search(str(code).upper())
    return f'{match.group(1)} {match.group(2)}' if match else None


def analyze(pdf_files: list[tuple[str, bytes]], catalog: pd.DataFrame):
    """Return course summary, appearances, subject placeholders, and PDF audit tables."""
    titles={normalize_code(row['Course Code']):str(row['Course Title']) for _,row in catalog.iterrows()}
    titles.pop(None,None)
    appearances=[]; placeholders=[]; audit=[]
    for name,blob in pdf_files:
        try:
            document=fitz.open(stream=blob,filetype='pdf')
            found={}; loose=set()
            for page_no,page in enumerate(document,1):
                words=page.get_text('words',sort=True)
                groups=defaultdict(list)
                for w in words:
                    groups[round(w[3]/3)*3].append(w)
                for group in groups.values():
                    group.sort(key=lambda w:w[0])
                    line=' '.join(w[4] for w in group)
                    for m in COURSE_PATTERN.finditer(line.upper()):
                        code=f'{m.group(1)} {m.group(2)}'
                        found.setdefault(code,set()).add(page_no)
                # PDF visual rows can merge words from two columns, so inspect
                # each original text line separately for subject-only requirements.
                for raw_line in page.get_text('text').splitlines():
                    cleaned=raw_line.strip().upper()
                    p=SUBJECT_PATTERN.search(cleaned)
                    if p:
                        subject=next((value for value in p.groups() if value),None)
                        if subject in {'RS','HIST','PHIL','ENG','ECON','MATH','BIO','CHEM','COM','PSY','SOC','ART','THEA','PHSC','ENVS','GEOG','POL','CRJ','ANTH'}:
                            loose.add((subject,raw_line.strip(),page_no))
            for code,pages in sorted(found.items()):
                appearances.append({'Program sheet':name,'Course code':code,'Catalog title':titles.get(code,''),'In Jane catalog':'Yes' if code in titles else 'Review','Pages':', '.join(map(str,sorted(pages)))})
            for subj,raw,page_no in sorted(loose):
                placeholders.append({'Program sheet':name,'Subject':subj,'PDF text':raw,'Page':page_no,'Interpretation':'Subject-only / unspecified course; not counted as a numbered course'})
            audit.append({'Program sheet':name,'Pages':len(document),'Numbered courses found':len(found),'Subject-only entries':len(loose),'Status':'Review — no numbered courses' if not found else 'Extracted'})
        except Exception as exc:
            audit.append({'Program sheet':name,'Pages':0,'Numbered courses found':0,'Subject-only entries':0,'Status':f'Error: {exc}'})
    detail=pd.DataFrame(appearances,columns=['Program sheet','Course code','Catalog title','In Jane catalog','Pages'])
    subjects=pd.DataFrame(placeholders,columns=['Program sheet','Subject','PDF text','Page','Interpretation'])
    audit_frame=pd.DataFrame(audit)
    if detail.empty:
        summary=pd.DataFrame(columns=['Course code','Catalog title','Number of program sheets','Program sheets','Jane catalog match'])
    else:
        summary=detail.groupby('Course code',as_index=False).agg(**{
            'Number of program sheets':('Program sheet','nunique'),
            'Program sheets':('Program sheet',lambda x:'; '.join(sorted(set(x)))),
            'Catalog title':('Catalog title','first'),
            'Jane catalog match':('In Jane catalog','first'),
        }).sort_values(['Number of program sheets','Course code'],ascending=[False,True])
        summary=summary[['Course code','Catalog title','Number of program sheets','Program sheets','Jane catalog match']]
    return summary,detail,subjects,audit_frame


def to_excel(frames: list[tuple[str,pd.DataFrame]]) -> bytes:
    output=BytesIO()
    with pd.ExcelWriter(output,engine='xlsxwriter') as writer:
        workbook=writer.book
        heading=workbook.add_format({'bold':True,'bg_color':'#17365D','font_color':'#FFFFFF','text_wrap':True,'valign':'vcenter'})
        for name,frame in frames:
            frame.to_excel(writer,sheet_name=name,index=False)
            ws=writer.sheets[name]
            ws.freeze_panes(1,0)
            ws.set_row(0,34,heading)
            ws.autofilter(0,0,max(1,len(frame)),max(0,len(frame.columns)-1))
            for i,column in enumerate(frame.columns):
                width={'Program sheets':65,'Program sheet':55,'Catalog title':43,'PDF text':55,'Status':36,'Interpretation':57}.get(column,24)
                ws.set_column(i,i,width)
            ws.set_landscape()
            ws.fit_to_pages(1,0)
    return output.getvalue()
