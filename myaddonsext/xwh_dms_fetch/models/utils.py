import base64
import os.path
from datetime import datetime
from PyPDF2 import PdfFileReader


def get_slide_type(file_ext):
    if file_ext in ['jpg', 'gif', 'bmp']:
        return 'infographic'
    elif file_ext in ['pdf', 'word', 'xls', 'ppt']:
        return 'document'
    else:
        return 'document'


def get_file_info(relpah, fullpath):
    stat = os.stat(fullpath)
    path = fullpath[len(relpah):]
    tmp = os.path.split(path)
    file_path = tmp[0]
    file_name = tmp[1]
    if file_path[0] == '/':
        file_path = file_path[1:]
    file_ext = os.path.splitext(file_name)[1]
    name = file_name[:-len(file_ext)]

    return {
        'relpath': relpah,
        'fullpath': fullpath,
        'file_create_date': datetime.fromtimestamp(stat.st_ctime),
        'file_update_date': datetime.fromtimestamp(stat.st_mtime),
        'file_ext': file_ext,
        'file_path': file_path,
        'file_name': file_name,
        'file_size': stat.st_size,
        'name': name
    }


def get_file_content(fullpath):
    file = open(fullpath, mode='rb')
    datas = base64.encodestring(file.read())
    file.close()
    return datas


def getPdfContent(filename):
    pdf = PdfFileReader(open(filename, "rb"))
    information = pdf.getDocumentInfo()
    number_of_pages = pdf.getNumPages()

    content = f"""
            Information about {filename}
            Author: {information.author}
            Creator: {information.creator}
            Producer: {information.producer}
            Subject: {information.subject}
            Title: {information.title}
            Number of pages: {number_of_pages}
            """
    for i in range(0, pdf.getNumPages()):
        pageObj = pdf.getPage(i)
        extractedText = pageObj.extractText()
        content += extractedText + "\n"
    return content
