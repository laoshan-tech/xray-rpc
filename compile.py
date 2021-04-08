import datetime
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import httpx

XRAY_GITHUB_USER = "XTLS"
XRAY_GITHUB_REPO = "Xray-core"
client = httpx.Client(timeout=httpx.Timeout(timeout=10, connect=15))
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def download(url: str, target: Path) -> bool:
    """
    下载文件
    :param url:
    :param target: 保存文件路径
    :return: 是否成功
    """
    with open(target, "wb") as f:
        try:
            with client.stream(method="GET", url=url) as resp:
                logger.info(f"下载 {url} 开始......")
                for chunk in resp.iter_bytes():
                    f.write(chunk)

            logger.info(f"从 {url} 下载文件到 {target} 成功")
            return True
        except Exception as e:
            logger.error(f"从 {url} 下载文件到 {target} 失败，{e}")
            return False


class XrayFile(object):
    def __init__(self, install_path: Path = None, use_cdn: bool = False):
        """
        xray-core文件目录相关
        :param install_path: 安装目录
        :param use_cdn: 是否使用CDN加速下载
        """
        if install_path is None:
            self.path = Path().home() / "xray-node"
        else:
            self.path = install_path

        self.use_cdn = use_cdn
        self.platform = "macos" if platform.system().lower() == "darwin" else platform.system().lower()
        self.arch = 64 if platform.machine().endswith("64") else 32

    @property
    def xray_install_path(self) -> Path:
        """
        xray-core安装目录
        :return:
        """
        return self.path

    @property
    def xray_zip_fn(self) -> Path:
        """
        xray-core压缩包路径
        :return:
        """
        return self.path / f"xray-core.zip"

    @property
    def xray_src_download_url_fmt(self) -> str:
        """
        xray-core下载URL，需要填充tag
        :return:
        """
        if self.use_cdn:
            return f"https://download.fastgit.org/{XRAY_GITHUB_USER}/{XRAY_GITHUB_REPO}/archive/refs/tags/{{tag}}.zip"
        else:
            return f"https://github.com/{XRAY_GITHUB_USER}/{XRAY_GITHUB_REPO}/archive/refs/tags/{{tag}}.zip"


def _unzip_xray_core(xray_f: XrayFile) -> bool:
    """
    解压xray-core
    :param xray_f:
    :return:
    """
    if xray_f.xray_zip_fn.exists():
        zip_file = zipfile.ZipFile(xray_f.xray_zip_fn, "r")
        for f in zip_file.namelist():
            zip_file.extract(f, xray_f.xray_zip_fn.parent)
        zip_file.close()
        return True
    else:
        logger.warning(f"{xray_f.xray_zip_fn} 不存在")
        return False


def _get_latest_xray_release() -> str:
    """
    获取最新的release版本
    :return:
    """
    req = client.get(f"https://api.github.com/repos/{XRAY_GITHUB_USER}/{XRAY_GITHUB_REPO}/releases/latest")
    if req.status_code != 200:
        logger.error(f"获取 xray-core 最新 release 版本失败，状态码 {req.status_code}")
        return ""

    result = req.json()
    latest_tag = result["tag_name"]
    return latest_tag


def _download_xray_zip(xray_f: XrayFile) -> bool:
    """
    下载xray-core
    :param xray_f:
    :return:
    """
    try:
        req = client.get(f"https://api.github.com/repos/{XRAY_GITHUB_USER}/{XRAY_GITHUB_REPO}/releases/latest")
        if req.status_code != 200:
            logger.error(f"获取 xray-core 最新 release 版本失败，状态码 {req.status_code}")
            return False

        result = req.json()
        latest_tag = result["tag_name"]

        download_success = download(
            url=xray_f.xray_src_download_url_fmt.format(tag=latest_tag), target=xray_f.xray_zip_fn
        )
        if download_success:
            logger.info(f"下载 xray-core 成功")
            return True
        else:
            return False
    except Exception as e:
        logger.exception(f"下载 xray-core 失败，{e}")
        return False


def _prepare_install(xray_f: XrayFile) -> bool:
    """
    安装前的准备
    :param xray_f: XrayFile 对象
    :return:
    """

    try:
        if not xray_f.xray_install_path.exists():
            xray_f.xray_install_path.mkdir(mode=0o755)
        return True
    except OSError as e:
        logger.exception(f"创建 xray-node 目录失败，{e}")
        return False


def install_xray(install_path: Path = None, use_cdn: bool = False) -> bool:
    """
    安装xray-core
    :param install_path: 指定安装目录
    :param use_cdn: 是否使用CDN加速下载
    :return:
    """
    if install_path is None:
        path = Path.home() / "xray-node"
    else:
        path = install_path

    xray_file = XrayFile(install_path=path, use_cdn=use_cdn)

    if not _prepare_install(xray_f=xray_file):
        return False

    if _download_xray_zip(xray_f=xray_file) and _unzip_xray_core(xray_f=xray_file):
        logger.info(f"成功安装 xray-core 至 {xray_file.xray_install_path}")
        return True
    else:
        return False


def gen_pb2(src: Path, dst: Path):
    """
    从xray源码生成pb2文件
    :param src:
    :param dst:
    :return:
    """
    # 创建生成目录
    shutil.rmtree(path=dst, ignore_errors=True)
    dst.mkdir(mode=0o755)

    # 扫描proto文件
    all_files = [str(f.absolute()) for f in src.rglob("*.proto")]

    # 编译
    command = (
        f"{sys.executable} -m grpc.tools.protoc "
        f"-I={src.absolute()} "
        f"--python_out={dst.absolute()} "
        f"--grpc_python_out={dst.absolute()} " + " ".join(all_files)
    )
    result = os.system(command)
    return result


def main():
    path = Path(__file__).parent / "xray_download"
    install_xray(install_path=path, use_cdn=True)

    latest_version = _get_latest_xray_release()
    logger.info(f"xray-core 最新版本为 {latest_version}")

    src_path = path / f"Xray-core-{latest_version.replace('v', '')}"
    dst_path = Path(__file__).parent / "xray_rpc"

    if src_path.exists():
        gen_pb2(src=src_path, dst=dst_path)
        logger.info(f"成功生成 RPC 至 {dst_path} 路径下")
        # 由于gRPC生成的代码在Python 3下存在诡异的引用问题，添加相对引用
        for py in dst_path.rglob("*.py"):
            with open(py, "r+") as f:
                code = f.read()
                f.seek(0)
                f.write(re.sub(r"from\s+(.*)\s+import (.*)pb2", r"from xray_rpc.\1 import \2pb2", code))
                f.truncate()

        p = subprocess.run(
            args=["poetry", "version", "-s"],
            timeout=2,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )
        current_pypi_version = p.stdout.strip()
        if str(current_pypi_version).startswith(latest_version.replace("v", "")):
            logger.info(f"当前 PyPi 版本 {current_pypi_version} 与 xray-core 版本 {latest_version} 相同，附加小版本")
            new_version = f"{latest_version.replace('v', '')}.{datetime.datetime.now().strftime('%Y%m%d%H%M')}"
            logger.info(new_version)
            os.system(command=f"poetry version {new_version}")
        else:
            logger.info(f"当前 PyPi 版本 {current_pypi_version} 与 xray-core 版本 {latest_version} 不同，跟进 xray-core 版本")
            os.system(command=f"poetry version {latest_version.replace('v', '')}")
    else:
        logger.error(f"{src_path} 不存在")


if __name__ == "__main__":
    main()
