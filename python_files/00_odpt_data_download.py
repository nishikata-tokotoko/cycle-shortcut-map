# JSON形式のデータをダウンロードする

import urllib.request
import json
import os

# URLの設定
dump_uri = "https://api.odpt.org/api/v4/"
dump_uri_challenge =  "https://api-challenge2024.odpt.org/api/v4/"

# ダウンロードするファイル
file_names = [
    'odpt:Calendar.json',
    'odpt:Operator.json',
    'odpt:Station.json',
    'odpt:StationTimetable.json',
    'odpt:TrainTimetable.json',
    'odpt:TrainType.json',
    'odpt:RailDirection.json',
    'odpt:Railway.json',
    'odpt:RailwayFare.json',
    'odpt:PassengerSurvey.json',
]

# アクセストークン
# 各自で取得したものをここに保存
token_odpt = 'your_access_token'
token_challenge = 'your_access_token_challenge'

# 保存先
path_odpt = os.path.join('..', 'data', 'odpt_api', 'open')
path_challenge = os.path.join('..', 'data', 'odpt_api', 'challenge')

# 保存先ディレクトリが存在しない場合は作成
os.makedirs(path_odpt, exist_ok = True)
os.makedirs(path_challenge, exist_ok = True)

# 通常ファイルをダウンロード
for f in file_names:
    print(f'Downloading {f}')

    endpoint = dump_uri + f + '?acl:consumerKey=' + token_odpt
    file_path = path_odpt + f.split(':')[-1]

    print(f'Fetching data from {endpoint}')
    with urllib.request.urlopen(endpoint) as url:
        data = json.load(url)

    print(f'Saving to {file_path}')
    with open(file_path, 'w') as output:
        json.dump(data, output)
    
    print('File saved.')

# チャレンジ限定データをダウンロード
for f in file_names:
    print(f'Downloading {f}')

    endpoint = dump_uri_challenge + f + '?acl:consumerKey=' + token_challenge
    file_path = path_challenge + f.split(':')[-1]

    print(f'Fetching data from {endpoint}')
    with urllib.request.urlopen(endpoint) as url:
        data = json.load(url)

    print(f'Saving to {file_path}')
    with open(file_path, 'w') as output:
        json.dump(data, output)
    
    print('File saved.')

# ----- GBFSデータのダウンロード -----

# 保存先ディレクトリが存在しない場合は作成
path = os.path.join('..', 'data', 'gbfs')
os.makedirs(path, exist_ok = True)

# 事業者の一覧
operators = ['docomo-cycle', 'docomo-cycle-tokyo', 'hellocycling']

# 事業者ごとにデータをダウンロード
for op in operators:
    os.makedirs(os.path.join(path, op), exist_ok = True)

    endpoint = 'https://api-public.odpt.org/api/v4/gbfs/' + op + '/gbfs.json'

    # データをロード
    with urllib.request.urlopen(endpoint) as url:
        data = json.load(url)
    with open(os.path.join(path, op, 'gbfs.json'), 'w', encoding = 'utf-8') as output:
        json.dump(data, output, ensure_ascii = False)

    # データに記載のエンドポイントから追加でダウンロード    
    for feed in data['data']['ja']['feeds']:
        feed_url = feed['url']
        feed_fn = feed['name'] + '.json'

        if feed_url == endpoint:
            continue

        with urllib.request.urlopen(feed_url) as feed_req:
            feed_data = json.load(feed_req)
        with open(os.path.join(path, op, feed_fn), 'w', encoding = 'utf-8') as feed_output:
            json.dump(feed_data, feed_output, ensure_ascii = False)

# GeoJSONに置き換え
for op in operators:

    with open(os.path.join('data', 'gbfs', op, 'station_information.json'), 'r', encoding = 'utf-8') as f:
        d = json.load(f)

    # initialise GeoJSON data
    geojson_data = {
        'type': 'FeatureCollection',
        'features': []
    }

    for station in d['data']['stations']:
        # initialise feature
        feature = {
            'type': 'Feature',
            'geometry': {
                'coordinates': [station['lon'], station['lat']],
                'type': 'Point'
            },
            'properties': {
                'operator': op
            }
        }

        # add properties
        for key, value in station.items():
            if key in ['lon', 'lat']:
                continue
            feature['properties'][key] = value
        
        # append
        geojson_data['features'].append(feature)
    
    with open(os.path.join('..', 'data', 'gbfs', op, 'station_information.geojson'), 'w', encoding = 'utf-8') as geojson_output:
            json.dump(geojson_data, geojson_output, ensure_ascii = False)
