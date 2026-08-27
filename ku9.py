import requests
from bs4 import BeautifulSoup
import json
import html
import re
import os
import zipfile
import hashlib

def calculate_zip_hash_without_timestamp(zip_path):
    """计算 zip 文件内容的哈希值，忽略文件时间戳"""
    hash_md5 = hashlib.md5()
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for file_info in sorted(zip_ref.infolist(), key=lambda x: x.filename):
            # 读取文件内容而不是时间戳
            with zip_ref.open(file_info.filename) as file:
                while chunk := file.read(4096):
                    hash_md5.update(chunk)
    return hash_md5.hexdigest()

def create_zip(zip_path, icon_dir, new_epg_data_path):
    """创建新的 ZIP 文件"""
    with zipfile.ZipFile(zip_path, 'w') as icon_zip:
        for icon_file in os.listdir(icon_dir):
            icon_zip.write(os.path.join(icon_dir, icon_file), arcname=icon_file)
        icon_zip.write(new_epg_data_path, arcname='epg_data.json')

def fetch_alias_data(local_path='ku9/alias.json'):
    """获取频道别名数据，优先在线，失败则使用本地文件"""
    try:
        response = requests.get('https://epg.112114.xyz/alias', timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')
        alias_data = {}

        for p in soup.find_all('p'):
            content = html.unescape(p.decode_contents())
            for line in content.split('\n'):
                line = line.strip()
                if '-->' in line:
                    alias, channel = map(str.strip, re.split(r'\s*-->\s*', line))
                    alias_data.setdefault(channel.upper(), []).append(alias.upper())

        formatted = {
            channel: ','.join(aliases)
            for channel, aliases in alias_data.items()
        }

        print('alias 在线获取成功')
        return formatted

    except Exception as e:
        print(f'alias 在线获取失败，尝试使用本地文件：{e}')

        if os.path.exists(local_path):
            try:
                with open(local_path, 'r', encoding='utf-8') as f:
                    print('使用本地 alias.json')
                    return json.load(f)
            except Exception as e:
                print(f'本地 alias.json 读取失败：{e}')

        print('未获取到 alias，使用空别名')
        return {}

def generate_epg_data(icon_data, formatted_alias):
    """生成 EPG 数据"""
    epg_data = {"epgs": []}
    for channel, logo in icon_data.items():
        channel_upper = channel.upper()
        aliases = formatted_alias.get(channel_upper, '').split(',')
        name_field = ','.join([channel_upper] + aliases)
        epg_data["epgs"].append({
            "epgid": channel,
            "logo": logo,
            "name": name_field
        })
    return epg_data

# 主程序逻辑
os.makedirs('ku9', exist_ok=True)

formatted_alias = fetch_alias_data()
with open('ku9/alias.json', 'w', encoding='utf-8') as alias_file:
    json.dump(formatted_alias, alias_file, ensure_ascii=False, indent=2)

with open('iconList_default.json', 'r', encoding='utf-8') as icon_file:
    icon_data = json.load(icon_file)

epg_data = generate_epg_data(icon_data, formatted_alias)
with open('ku9/epg_data.json', 'w', encoding='utf-8') as epg_file:
    json.dump(epg_data, epg_file, ensure_ascii=False, indent=2)

# 生成第二份 epg_data.json，logo 使用 epgid
new_epg_data = {"epgs": [{"epgid": channel["epgid"], "logo": channel["epgid"], "name": channel["name"]} for channel in epg_data["epgs"]]}

new_epg_data_path = 'ku9/new_epg_data.json'
with open(new_epg_data_path, 'w', encoding='utf-8') as new_epg_file:
    json.dump(new_epg_data, new_epg_file, ensure_ascii=False, indent=2)

# 创建临时 ZIP 文件并检查更新
temp_zip_path = 'ku9/temp_icon.zip'
create_zip(temp_zip_path, 'icon', new_epg_data_path)

zip_path = 'ku9/icon.zip'
if os.path.exists(zip_path) and calculate_zip_hash_without_timestamp(zip_path) == calculate_zip_hash_without_timestamp(temp_zip_path):
    print("icon.zip 文件没有变化，未更新。")
    os.remove(temp_zip_path)
else:
    print("icon.zip 文件已更新。")
    os.replace(temp_zip_path, zip_path)
