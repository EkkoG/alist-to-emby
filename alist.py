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
    files: list[dict],
    remote_path: str,
    local_path: str,
    overwrite_strm: bool,
):
    for file in files:
        file_name = file["name"]

        local_file_name = (
            f"{local_path}/{os.path.splitext(file_name)[0]}.strm"
            if is_video_file(file_name)
            else f"{local_path}/{file_name}"
        )

        is_overwrite = False
        if overwrite_strm and is_video_file(file_name) and os.path.exists(local_file_name):
            os.remove(local_file_name)
            is_overwrite = True

        if os.path.exists(local_file_name):
            print(f"文件 {local_file_name} 已存在, 跳过")
        else:
            url = f"{HOST}/d{remote_path}/{file_name}"
            # add sign when not empty
            if "sign" in file and file["sign"] and file["sign"] != "":
                url = f"{url}?sign={file['sign']}"
            if is_video_file(file_name):
                write_strm(url, local_file_name)
                if is_overwrite:
                    print(f"{url} 已写入 {local_file_name}, 覆盖已存在的 strm 文件")
                else:
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
    dirs: list[dict],
    remote_path: str,
    local_path: str,
    token,
    overwrite_strm: bool,
):
    count = 0
    for dir in dirs:
        file_name = dir["name"]

        if file_name.endswith("@eaDir"):
            continue

        count += 1
        print(f"正在克隆目录 {file_name}, 进度: {count}/{len(dirs)}")

        while executor._work_queue.qsize() >= executor._max_workers * 10:
            time.sleep(1)
        clone_dir(
            f"{remote_path}/{file_name}",
            f"{local_path}/{file_name}",
            token,
            overwrite_strm,
        )


def clone_dir(
    remote_path: str, local_path: str, token: str, overwrite_strm: bool
):
    start = time.time()
    resp = list_files(token, remote_path)
    print(f"{remote_path}：获取文件列表耗时: {time.time() - start}")
    all_files = resp["data"]["content"]
    if not all_files:
        print(f"{remote_path} 无文件")
        return
    dirs = list(filter(lambda x: x["is_dir"], all_files))
    files = list(filter(lambda x: is_file_need_proccess(x["name"]) and not x["is_dir"], all_files))
    dirs.sort(key=lambda x: x["name"])
    files.sort(key=lambda x: x["name"])

    print(f"{remote_path}: {len(dirs)} 个目录, {len(files)} 个文件")

    if not os.path.exists(local_path):
        os.makedirs(local_path)

    clone_files(files, remote_path, local_path, overwrite_strm)
    clone_sub_dir(dirs, remote_path, local_path, token, overwrite_strm)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="克隆 alist 目录到本地, 视频文件将生成 strm 文件"
    )
    parser.add_argument("--remote_path", type=str, help="alist 目录", required=True)
    parser.add_argument("--local_path", type=str, help="本地目录", required=True)
    parser.add_argument("--username", type=str, help="alist 用户名", required=True)
    parser.add_argument(
        "--password", type=str, help="alist 密码， 或者使用 ALIST_PASSWORD 环境变量"
    )
    parser.add_argument("--host", type=str, help="alist 服务器地址", required=True)
    parser.add_argument("--threads", type=int, help="文件下载的线程数", default=5)
    parser.add_argument("--use_temp", action="store_true", help="是否使用临时目录")
    parser.add_argument(
        "--tmp_dir", type=str, help="临时目录路径", default="/tmp/alist-strm"
    )
    parser.add_argument(
        "--overwrite_strm", action="store_true", help="是否覆盖已存在的 strm 文件"
    )

    args = parser.parse_args()
    if args.password is None:
        args.password = os.getenv("ALIST_PASSWORD")
        if args.password is None:
            raise Exception(
                "password is required, please use --password or set ALIST_PASSWORD env variable"
            )

    HOST = args.host
    token = login(args.username, args.password)
    executor = ThreadPoolExecutor(max_workers=args.threads)
    local_path = os.path.normpath(args.local_path)
    remote_path = os.path.normpath(args.remote_path)

    if args.use_temp:
        path = os.path.normpath(args.tmp_dir) + "/" + local_path.split("/")[-1]
    else:
        path = local_path

    clone_dir(remote_path, path, token, args.overwrite_strm)
    # wait for all tasks done
    executor.shutdown(wait=True)
    if args.use_temp:
        print(f"文件已克隆到: {path}")
        # copy to local path
        shutil.copytree(path, local_path, dirs_exist_ok=True)
        print(f"文件已拷贝到: {local_path}")
