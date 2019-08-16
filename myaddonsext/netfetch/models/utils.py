import base64
import os.path
from datetime import datetime


def get_slide_type(file_ext):
    if file_ext in ['jpg', 'gif', 'bmp']:
        return 'infographic'
    elif file_ext in ['pdf', 'word', 'xls', 'ppt']:
        return 'document'
    else:
        return 'document'


def get_file_info(rootpath, fullpath):
    stat = os.stat(fullpath)
    file_path = fullpath[len(rootpath):]
    if file_path[0] == '/':
        file_path = file_path[1:]
    file_ext = os.path.splitext(file_path)[1]
    dirs = os.path.split(file_path)[0].split('/')
    if len(dirs) > 0 and dirs[0] == '':
        dirs.pop(0)
    return {
        'fullpath': fullpath,
        'file_create_date': datetime.fromtimestamp(stat.st_ctime),
        'file_update_date': datetime.fromtimestamp(stat.st_mtime),
        'file_ext': file_ext[1:] if len(file_ext) > 0 else '',
        'file_path': file_path,
        'dirs': dirs,
        'file_name': file_path[:-len(file_ext)],
        'name': os.path.split(file_path)[1][:-len(file_ext)]
    }


def get_file_content(fullpath):
    file = open(fullpath, mode='rb')
    datas = base64.encodestring(file.read())
    file.close()
    return datas
