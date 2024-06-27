import requests
import os
import argparse
import time

HOST=''

def login(username: str, password: str):
    url = HOST + '/api/auth/login'
    data = {
        'Username': username,
        'Password': password
    }
    res = requests.post(url, data=data)
    resp = res.json()
    if resp['code'] == 200:
        token = resp['data']['token']
        return token
    else:
        # throw error
        raise Exception('login failed')

def list_files(token: str, path: str):
    url = HOST + '/api/fs/list'
    headers = {
        'Authorization': f'{token}'
    }
    data = {
        'path': path
    }
    res = requests.post(url, headers=headers, data=data)
    return res.json()

def is_video_file(file: str):
    exts = ['.mp4', '.mkv', '.avi', '.rmvb', '.rm', '.flv', '.mov', '.wmv', '.asf', '.ts', '.webm', '.mpeg', '.mpg', '.m4v']
    for ext in exts:
        if file.endswith(ext):
            return True
    return False

def is_image_file(file: str):
    exts = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff']
    for ext in exts:
        if file.endswith(ext):
            return True
    return False

def is_nfo_file(file: str):
    exts = ['.nfo']
    for ext in exts:
        if file.endswith(ext):
            return True
    return False

def is_subtitle_file(file: str):
    exts = ['.srt', '.ass', '.ssa', '.sub', '.vtt']
    for ext in exts:
        if file.endswith(ext):
            return True
    return False

def get_file_info(token: str, path: str):
    url = HOST + '/api/fs/get'
    headers = {
        'Authorization': f'{token}'
    }
    data = {
        "path": path
    }
    res = requests.post(url, headers=headers, data=data)
    return res.json()

def clone_dir(remote_path: str, local_path: str, token: str):
    resp = list_files(token, remote_path)
    files = resp['data']['content']
    count = 0
    for file in files:
        count += 1
        print(f"当前目录: {remote_path}, 当前文件: {file['name']}, 进度: {count}/{len(files)}")
        if not os.path.exists(local_path):
            os.makedirs(local_path)

        if is_video_file(file['name']):
            name_without_ext = os.path.splitext(file['name'])[0]
            strm = f"{local_path}/{name_without_ext}.strm"
            if os.path.exists(strm):
                print(f"文件 {file['name']} 已存在, 跳过")
            else:
                info = get_file_info(token, f"{remote_path}/{file['name']}")['data']
                with open(strm, 'w') as f:
                    f.write(f"{HOST}/d{remote_path}/{file['name']}?sign={info['sign']}")
        elif is_image_file(file['name']) or is_nfo_file(file['name']) or is_subtitle_file(file['name']):
            if os.path.exists(f"{local_path}/{file['name']}"):
                print(f"文件 {file['name']} 已存在, 跳过")
            else:
                info = get_file_info(token, f"{remote_path}/{file['name']}")['data']
                with open(f"{local_path}/{file['name']}", 'wb') as f:
                    try:
                        f.write(requests.get(f"{HOST}/d{remote_path}/{file['name']}?sign={info['sign']}").content)
                    except Exception as e:
                        print(e)
                
                # time.sleep(1)
        elif file['is_dir']:
            if not os.path.exists(f"{local_path}/{file['name']}"):
                os.makedirs(f"{local_path}/{file['name']}")
            clone_dir(f"{remote_path}/{file['name']}", f"{local_path}/{file['name']}", token)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Clone the remote directory to local')
    parser.add_argument('--remote_path', type=str, help="remote path", required=True)
    parser.add_argument('--local_path', type=str, help="local path", required=True)
    parser.add_argument('--username', type=str, help="username", required=True)
    parser.add_argument('--password', type=str, help="password", required=True)
    parser.add_argument('--host', type=str, help="host", required=True)

    args = parser.parse_args()

    HOST = args.host
    token = login(args.username, args.password)
    clone_dir(args.remote_path, args.local_path, token)
     
