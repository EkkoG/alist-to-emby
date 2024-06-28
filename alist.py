import requests
import os
import argparse
import time
from concurrent.futures import ThreadPoolExecutor
import shutil

HOST = ""
executor = None


def login(username: str, password: str):
    url = HOST + "/api/auth/login"
    data = {"Username": username, "Password": password}
    res = requests.post(url, data=data)
    resp = res.json()
    if resp["code"] == 200:
        token = resp["data"]["token"]
        return token
    else:
        # throw error
        raise Exception("login failed")


def list_files(token: str, path: str):
    url = HOST + "/api/fs/list"
    headers = {"Authorization": f"{token}"}
    data = {"path": path}
    res = requests.post(url, headers=headers, data=data)
    return res.json()


def is_video_file(file: str):
    exts = [
        ".mp4",
        ".mkv",
        ".avi",
        ".rmvb",
        ".rm",
        ".flv",
        ".mov",
        ".wmv",
        ".asf",
        ".ts",
        ".webm",
        ".mpeg",
        ".mpg",
        ".m4v",
    ]
    for ext in exts:
        if file.endswith(ext):
            return True
    return False


def is_image_file(file: str):
    exts = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"]
    for ext in exts:
        if file.endswith(ext):
            return True
    return False


def is_nfo_file(file: str):
    exts = [".nfo"]
    for ext in exts:
        if file.endswith(ext):
            return True
    return False


def is_subtitle_file(file: str):
    exts = [".srt", ".ass", ".ssa", ".sub", ".vtt"]
    for ext in exts:
        if file.endswith(ext):
            return True
    return False


def get_file_info(token: str, path: str):
    url = HOST + "/api/fs/get"
    headers = {"Authorization": f"{token}"}
    data = {"path": path}
    res = requests.post(url, headers=headers, data=data)
    return res.json()


def is_file_need_proccess(file: str) -> bool:
    return (
        is_image_file(file)
        or is_subtitle_file(file)
        or is_nfo_file(file)
        or is_video_file(file)
    )


def download(url: str, to: str):
    print(f"{url} 开始下载")
    with open(to, "wb") as f:
        try:
            f.write(requests.get(url).content)
            print(f"{url} 下载完成")
        except Exception as e:
            print(e)
            print(f"{url} 下载完成失败")


def write_strm(url: str, to: str):
    with open(to, "w") as f:
        f.write(url)


def clone_files(
    files: list[dict], remote_path: str, local_path: str, token, sign: bool
):
    count = 0
    for file in files:
        count += 1

        file_name = file["name"]
        if file_name.endswith("@eaDir"):
            continue

        local_file_name = (
            f"{local_path}/{os.path.splitext(file_name)[0]}.strm"
            if is_video_file(file_name)
            else f"{local_path}/{file_name}"
        )
        if os.path.exists(local_file_name):
            print(f"文件 {local_file_name} 已存在, 跳过")
        else:
            url = f"{HOST}/d{remote_path}/{file_name}"
            if sign:
                start = time.time()
                info = get_file_info(token, f"{remote_path}/{file_name}")["data"]
                url = f"{url}?sign={info['sign']}"
                print(f"获取文件信息耗时: {time.time() - start}")
            if is_video_file(file_name):
                write_strm(url, local_file_name)
                print(f"{url} 已写入 {local_file_name}")
            else:

                def _download(url, local_file_name):
                    download(url, local_file_name)
                    print(f"剩余任务数: {executor._work_queue.qsize()}")

                executor.submit(_download, url, local_file_name)
                print(
                    f"{url} 已提交下载任务, 剩余任务数: {executor._work_queue.qsize()}"
                )


def clone_sub_dir(
    dirs: list[dict], remote_path: str, local_path: str, token, sign: bool
):
    count = 0
    for dir in dirs:
        count += 1
        print(f"正在克隆目录 {dir['name']}, 进度: {count}/{len(dirs)}")

        file_name = dir["name"]
        while executor._work_queue.qsize() >= executor._max_workers * 10:
            time.sleep(1)
        clone_dir(
            f"{remote_path}/{file_name}", f"{local_path}/{file_name}", token, sign
        )


def clone_dir(remote_path: str, local_path: str, token: str, sign: bool):
    start = time.time()
    resp = list_files(token, remote_path)
    print(f"{remote_path}：获取文件列表耗时: {time.time() - start}")
    files = resp["data"]["content"]
    dirs = list(filter(lambda x: x["is_dir"], files))
    files = list(filter(lambda x: is_file_need_proccess(x["name"]), files))
    dirs.sort(key=lambda x: x["name"])
    files.sort(key=lambda x: x["name"])

    print(f"{remote_path}: {len(dirs)} 个目录, {len(files)} 个文件")

    if not os.path.exists(local_path):
        os.makedirs(local_path)

    clone_files(files, remote_path, local_path, token, sign)
    clone_sub_dir(dirs, remote_path, local_path, token, sign)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clone the remote directory to local")
    parser.add_argument("--remote_path", type=str, help="remote path", required=True)
    parser.add_argument("--local_path", type=str, help="local path", required=True)
    parser.add_argument("--username", type=str, help="username", required=True)
    parser.add_argument("--password", type=str, help="password", required=True)
    parser.add_argument("--host", type=str, help="host", required=True)
    parser.add_argument("--sign", action="store_true", help="sign")
    parser.add_argument("--threads", type=int, help="threads", default=5)
    parser.add_argument("--use_temp", action="store_true", help="use temp")

    args = parser.parse_args()

    HOST = args.host
    token = login(args.username, args.password)
    executor = ThreadPoolExecutor(max_workers=args.threads)
    if args.use_temp:
        path = "/tmp/alist-strm/" + args.local_path.split("/")[-1]
    else:
        path = args.local_path

    clone_dir(args.remote_path, path, token, args.sign)
    # wait for all tasks done
    executor.shutdown(wait=True)
    if args.use_temp:
        print(f"文件已克隆到: {path}")
        # copy to local path
        shutil.copytree(path, args.local_path, dirs_exist_ok=True)
        print(f"文件已拷贝到: {args.local_path}")
