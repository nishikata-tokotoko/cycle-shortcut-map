# 乗換案内のためのデータ整理
# 乗換案内に用いるネットワークを路線時刻表から構築

import pandas as pd
import geopandas as gpd
import json
import os
import networkx as nx
import osmnx
import re
import pickle

from datetime import datetime

# 元のパス
path_odpt = os.path.join('..', 'data', 'odpt_api', 'challenge')

# 保存するパス
# 現在は同じだが必要に応じて変更
path_edit = os.path.join('data', 'odpt_api', 'challenge')

# 保存先のフォルダが存在しない場合は作成
os.makedirs(path_edit, exist_ok = True)

# 駅時刻表を読み込み
with open(os.path.join(path_odpt, 'StationTimetable.json'), 'r') as f:
    s_timetable_dict = json.load(f)

# 路線時刻表を読み込み
with open(os.path.join(path_odpt, 'TrainTimetable.json'), 'r') as f:
    t_timetable_dict = json.load(f)

# 平日昼間を定義
start_time = 10
end_time = 15

# ない路線を補完
edit_fp = os.path.join('..', 'data', 'ksj', 'edit')
os.makedirs(edit_fp, exist_ok = True)

with open(os.path.join(edit_fp, 'operators_edit.json'), 'r') as f:
    operator_dict = json.load(f)
with open(os.path.join(edit_fp, 'railways_edit.json'), 'r') as f:
    railway_dict = json.load(f)
with open(os.path.join(edit_fp, 'stations_edit.json'), 'r') as f:
    station_dict = json.load(f)
with open(os.path.join(edit_fp, 'train_type_edit.json'), 'r') as f:
    train_type = json.load(f)

# 平均待ち時間の算出
# 駅時刻表の本数から算出
waiting_time_dict = {}

for s in s_timetable_dict:
    # 平日以外はスキップ
    if s['odpt:calendar'] != 'odpt.Calendar:Weekday':
        continue
    
    # 駅のデータを作成
    station_id = s['odpt:station']
    if station_id not in waiting_time_dict:
        waiting_time_dict[station_id] = {}
    
    # 路線データを作成
    railway_id = s['odpt:railway']
    if railway_id not in waiting_time_dict[station_id]:
        waiting_time_dict[station_id][railway_id] = {}

    # 向きデータを作成
    direction_id = s['odpt:railDirection']
    waiting_time_dict[station_id][railway_id][direction_id] = {}

    # stationTimeTableObjectを日中だけにフィルター
    timetable_obj = [
        d for d in s['odpt:stationTimetableObject']
        if start_time <= int(d['odpt:departureTime'][:2]) <= end_time
    ]
    
    # 種別一覧を取得
    train_type_set = set([t['odpt:trainType'] for t in timetable_obj])

    # 種別ごとに本数から待ち時間を算出
    for t_type in train_type_set:
        num_trains = len([t for t in timetable_obj if t['odpt:trainType'] == t_type])
        wait_time = (((end_time - start_time) + 1) * 60 / num_trains) / 2
        
        waiting_time_dict[station_id][railway_id][direction_id][t_type] = wait_time

# 手入力データを追加
path_gen_edited = os.path.join('..', 'data', 'odpt_api', 'missing_generated_edited')
with open(os.path.join(path_gen_edited, 'waiting_time_dict.pkl'), 'rb') as f:
    waiting_time_added = pickle.load(f)

for station, data in waiting_time_added.items():
    if station in waiting_time_dict.keys():
        for dir, duration in data.items():
            waiting_time_dict[station][dir] = duration
    else:
        waiting_time_dict[station] = data

# 列車時刻表がある事業者
set([t['odpt:operator'] for t in t_timetable_dict])

# 列車時刻表の所要時間を使用
# 駅間所要時間のデータを初期化
duration_list = {}

for train in t_timetable_dict:
    # 平日以外はスキップ
    if train['odpt:calendar'] != 'odpt.Calendar:Weekday':
        continue   

    # 基本情報を抽出
    railway_id = train['odpt:railway']
    type_id = train['odpt:trainType']
    direction_id = train['odpt:railDirection']

    if railway_id not in duration_list:
        duration_list[railway_id] = {}
    if type_id not in duration_list[railway_id]:
        duration_list[railway_id][type_id] = {}
    if direction_id not in duration_list[railway_id][type_id]:
        duration_list[railway_id][type_id][direction_id] = {}
    
    # 時刻表データを抽出
    timetable_obj = train['odpt:trainTimetableObject']

    # 2駅間同士の組み合わせでループ
    for u,v in zip(timetable_obj[:-1], timetable_obj[1:]):
        # データが不完全なものは飛ばす
        if 'odpt:departureTime' not in u:
            continue
        # 出発時刻が昼間ではないものは飛ばす
        if not (start_time <= int(u['odpt:departureTime'][:2]) <= end_time):
            continue

        # 前駅出発時刻
        dept_station = u['odpt:departureStation']
        dept_time = u['odpt:departureTime']

        # 次駅到着時刻（ない場合は次駅出発時刻で代用）
        arr_station = ''
        arr_time = ''
        if ('odpt:arrivalTime' in v) and ('odpt:arrivalStation' in v):
            arr_station = v['odpt:arrivalStation']
            arr_time = v['odpt:arrivalTime']
        elif ('odpt:departureTime' in v) and ('odpt:departureStation' in v):
            arr_station = v['odpt:departureStation']
            arr_time = v['odpt:departureTime']
        # データが不完全の場合は飛ばす
        else:
            continue
        
        # 所要時間を計算
        time_format = '%H:%M'
        time_difference = (
            datetime.strptime(arr_time, time_format) - datetime.strptime(dept_time, time_format)
        ).total_seconds() / 60

        # 所要時間を保存
        # すでにこの組み合わせが存在する場合はリストに追加、ない場合は新たに作成
        if (dept_station, arr_station) not in duration_list[railway_id][type_id][direction_id]:
            duration_list[railway_id][type_id][direction_id][(dept_station, arr_station)] = {
                'duration_list': [time_difference]
            }
        else:
            duration_list[railway_id][type_id][direction_id][(dept_station, arr_station)]['duration_list'].append(time_difference)

# 平均所要時間を計算
for r in duration_list:
    for t in duration_list[r]:
        for d in duration_list[r][t]:
            for c in duration_list[r][t][d]:
                d_list = duration_list[r][t][d][c]['duration_list']
                duration_list[r][t][d][c]['duration_mins'] = sum(d_list) / len(d_list)

# 無いデータを補完

# 武蔵野線 船橋法典→西船橋
duration_list['odpt.Railway:JR-East.Musashino']['odpt.TrainType:JR-East.Local']['odpt.RailDirection:Outbound'][('odpt.Station:JR-East.Musashino.Funabashihoten', 'odpt.Station:JR-East.Musashino.NishiFunabashi')] = duration_list['odpt.Railway:JR-East.Musashino']['odpt.TrainType:JR-East.Local']['odpt.RailDirection:Inbound'][('odpt.Station:JR-East.Musashino.NishiFunabashi', 'odpt.Station:JR-East.Musashino.Funabashihoten')]

# 京葉線 南船橋→西船橋
duration_list['odpt.Railway:JR-East.Keiyo']['odpt.TrainType:JR-East.Local']['odpt.RailDirection:Inbound'][('odpt.Station:JR-East.Keiyo.MinamiFunabashi',
  'odpt.Station:JR-East.Keiyo.NishiFunabashi')] = duration_list['odpt.Railway:JR-East.Keiyo']['odpt.TrainType:JR-East.Local']['odpt.RailDirection:Outbound'][('odpt.Station:JR-East.Keiyo.NishiFunabashi',
  'odpt.Station:JR-East.Keiyo.MinamiFunabashi')]

# 京葉線 
duration_list['odpt.Railway:JR-East.Keiyo']['odpt.TrainType:JR-East.Local']['odpt.RailDirection:Outbound'][('odpt.Station:JR-East.Keiyo.Ichikawashiohama', 'odpt.Station:JR-East.Keiyo.NishiFunabashi')] = duration_list['odpt.Railway:JR-East.Keiyo']['odpt.TrainType:JR-East.Local']['odpt.RailDirection:Inbound'][('odpt.Station:JR-East.Keiyo.NishiFunabashi', 'odpt.Station:JR-East.Keiyo.Ichikawashiohama')]

# 手入力データを読み込み
path_edited = os.path.join('..', 'data', 'odpt_api', 'missing_edited')
with open(os.path.join(path_edited, 'duration_dict.pkl'), 'rb') as f:
    duration_list_added = pickle.load(f)
duration_list.update(duration_list_added)

# 駅名の重複を解決
# '入谷', '早稲田', '浅草', '小川町', '赤坂', '永田', '栄町', '平和台', 
# '豊島園' - 西武と都営は分ける
# '弘明寺' - 京急と市営地下鉄は分ける
# '市ヶ谷' と '市ケ谷' は揃える
# '押上(スカイツリー前)' と '押上〈スカイツリー前〉' と '押上' も揃える

# 修正する名前のdict
edit_names = {
    'odpt.Station:TokyoMetro.Hibiya.Iriya': '入谷（東京都）',
    'odpt.Station:JR-East.Sagami.Iriya': '入谷（神奈川県）',
    'odpt.Station:Toei.Arakawa.Waseda': '早稲田（都電）',
    'odpt.Station:TokyoMetro.Tozai.Waseda': '早稲田（東京メトロ）',
    'odpt.Station:MIR.TsukubaExpress.Asakusa': '浅草（TX）',
    'odpt.Station:Toei.Shinjuku.Ogawamachi': '小川町（東京都）',
    'odpt.Station:Tobu.Tojo.Ogawamachi': '小川町（埼玉県）',
    'odpt.Station:JR-East.Hachiko.Ogawamachi': '小川町（埼玉県）',
    'odpt.Station:Toei.Shinjuku.Ichigaya': '市ケ谷',
    'odpt.Station:TokyoMetro.Hanzomon.Oshiage': '押上',
    'odpt.Station:Tobu.TobuSkytreeBranch.Oshiage': '押上',
    'odpt.Station:Jomo.Jomo.Akasaka': '赤坂（群馬県）',
    'odpt.Station:TokyoMetro.Chiyoda.Akasaka': '赤坂（東京都）',
    'odpt.Station:Toei.Oedo.Toshimaen': '豊島園（都営）',
    'odpt.Station:Seibu.Toshima.Toshimaen': '豊島園（西武）',
    'odpt.Station:TokyoMetro.Fukutoshin.Heiwadai': '平和台（東京都）',
    'odpt.Station:TokyoMetro.Yurakucho.Heiwadai': '平和台（東京都）',
    'odpt.Station:Ryutetsu.Nagareyama.Heiwadai': '平和台（千葉県）',
    'odpt.Station:Toei.Arakawa.Sakaecho': '栄町（東京都）',
    'odpt.Station:ChibaMonorail.Line1.Sakaecho': '栄町（千葉県）',
    'odpt.Station:JR-East.Sotobo.Nagata': '永田（千葉県）',
    'odpt.Station:Chichibu.Chichibu.Nagata': '永田（埼玉県）',
    'odpt.Station:YokohamaMunicipal.Blue.Gumyoji': '弘明寺（市営地下鉄）',
    'odpt.Station:Keikyu.Main.Gumyoji': '弘明寺（京急）'
}

for n in station_dict:
    for key in edit_names.keys():
        if n['owl:sameAs'] == key:
            n['dc:title'] = edit_names[key]

# 隣接駅同士のリンクを作成
# データの初期化
adj_stations_list = []
type_dir_nodes = []

for r in duration_list:
    railway_str = r.split(':')[-1]
    for t in duration_list[r]:
        type_str = t.split(':')[-1]
        for d in duration_list[r][t]:
            direction_str = d.split(':')[-1]
            for (u, v) in duration_list[r][t][d]:
                # データを抽出
                dep_st = u.split(':')[-1]
                arr_st = v.split(':')[-1]
                weight = duration_list[r][t][d][(u,v)]['duration_mins']
                dep_node_name = '_'.join([dep_st, railway_str, direction_str, type_str])
                arr_node_name = '_'.join([arr_st, railway_str, direction_str, type_str])

                # edge_dataの形に整形
                link_data = (dep_node_name, arr_node_name, {
                    'link_type': 'train',
                    'railway': r,
                    'direction': d,
                    'train_type': t,
                    'duration': weight
                })

                # リストに追加
                adj_stations_list.append(link_data)

                # ノードデータの作成とリストへの追加
                if dep_node_name not in [n[0] for n in type_dir_nodes]:
                    dep_node_data = (dep_node_name, {
                        'node_type': 'train_node',
                        'station': u,
                        'railway': r,
                        'direction': d,
                        'train_type': t,
                    })
                    # データを追加で取得
                    station_data = [t for t in station_dict if t['owl:sameAs'] == u][0]
                    dep_node_data[1]['station_name'] = station_data['dc:title']
                    if ('geo:long' in station_data) and ('geo:lat' in station_data):
                        dep_node_data[1]['x'] = station_data['geo:long']
                        dep_node_data[1]['y'] = station_data['geo:lat']

                    type_dir_nodes.append(dep_node_data)

                # ノードデータの作成とリストへの追加
                if arr_node_name not in [n[0] for n in type_dir_nodes]:
                    arr_node_data = (arr_node_name, {
                        'node_type': 'train_node',
                        'station': v,
                        'railway': r,
                        'direction': d,
                        'train_type': t,
                    })

                    # データを追加で取得
                    station_data = [t for t in station_dict if t['owl:sameAs'] == v][0]
                    arr_node_data[1]['station_name'] = station_data['dc:title']
                    if ('geo:long' in station_data) and ('geo:lat' in station_data):
                        arr_node_data[1]['x'] = station_data['geo:long']
                        arr_node_data[1]['y'] = station_data['geo:lat']

                    type_dir_nodes.append(arr_node_data)           

# ----- 乗り降りリンクを作成 -----
# データの初期化
intra_station_links = []

for station, s_data in waiting_time_dict.items():
    for railway, r_data in s_data.items():
        for direction, d_data in r_data.items():
            for type, duration in d_data.items():

                # 種別・方面ノード名を作成
                node_name = '_'.join([
                    station.split(':')[-1],
                    railway.split(':')[-1],
                    direction.split(':')[-1],
                    type.split(':')[-1]
                ])

                # 乗車時のデータ
                on_data = (station, node_name, {
                    'link_type': 'on_off',
                    'on_off': 'on',
                    'station': station,
                    'railway': railway,
                    'direction': direction,
                    'train_type': type,
                    'duration': duration
                })

                intra_station_links.append(on_data)


# 降車リンクはすべての種別・方向ノードから所要時間ゼロで作成
for node in type_dir_nodes:
    node_data = node[1]
    off_data = (node[0], node_data['station'], {
        'link_type': 'on_off',
        'on_off': 'off',
        'station': node_data['station'],
        'railway': node_data['railway'],
        'direction': node_data['direction'],
        'train_type': node_data['train_type'],
        'duration': 0
    })
    intra_station_links.append(off_data)

# 直通駅を通過する系の対応
# 京急・エアポート快特：品川のノードをつなぐ
# スカイライナーは高砂を通過するので、青砥でスカイアクセスの線とつなぐ
# 特急ちちぶも吾野を通過することから、飯能で秩父線の線をつなぐ
# 降車ノードはすでに作成されているため追加不要
additional_links = [
    (
        'odpt.Station:Keikyu.Main.Shinagawa',
        'Keikyu.Main.Shinagawa_Keikyu.Airport_Outbound_Keikyu.AirportRapidLimitedExpress',
        [n[2] for n in intra_station_links if n[0] == 'odpt.Station:Keikyu.Main.Shinagawa' and n[1] == 'Keikyu.Main.Shinagawa_Keikyu.Main_Outbound_Keikyu.AirportRapidLimitedExpress'][0]
    ),
    (
        'odpt.Station:Keisei.Main.Aoto', 
        'Keisei.Main.Aoto_Keisei.NaritaSkyAccess_Inbound_Keisei.Skyliner',
        [n[2] for n in intra_station_links if n[0] == 'odpt.Station:Keisei.Main.Aoto' and n[1] == 'Keisei.Main.Aoto_Keisei.Main_Inbound_Keisei.Skyliner'][0]
    ),
    (
        'odpt.Station:Seibu.Ikebukuro.Hanno',
        'Seibu.Ikebukuro.Hanno_Seibu.SeibuChichibu_Outbound_Seibu.LimitedExpress',
        [n[2] for n in intra_station_links if n[0] == 'odpt.Station:Seibu.Ikebukuro.Hanno' and n[1] == 'Seibu.Ikebukuro.Hanno_Seibu.Ikebukuro_Outbound_Seibu.LimitedExpress'][0]
    )
]

additional_links[0][2]['railway'] = 'odpt.Railway:Keikyu.Airport'
additional_links[1][2]['railway'] = 'odpt.Railway:Keisei.NaritaSkyAccess'
additional_links[2][2]['railway'] = 'odpt.Railway:Seibu.SeibuChichibu'

intra_station_links = intra_station_links + additional_links

# ----- 乗り換えリンクの追加 -----
# 乗換駅リンクの一覧
transfer_links = []

# 駅ノードの一覧
station_nodes = []

for s in station_dict:
    u_id = s['owl:sameAs']
    u_name = s['dc:title']

    # 駅データの作成
    station_data = (u_id, {
        'node_type': 'station',
        # 'x': s['geo:long'],
        # 'y': s['geo:lat'],
        'station_name': s['dc:title'],
        'station_name_en': s['odpt:stationTitle']['en'],
        'railway': s['odpt:railway'],
        'operator': s['odpt:operator']
    })
    # 駅コードと位置情報はない場合もあり
    if 'odpt:stationCode' in s:
        station_data[1]['station_code'] = s['odpt:stationCode']
    if ('geo:long' in s) and ('geo:lat' in s):
        station_data[1]['x'] = s['geo:long']
        station_data[1]['y'] = s['geo:lat']

    station_nodes.append(station_data)

    if 'odpt:connectingStation' in s:
        for v in s['odpt:connectingStation']:
            v_data = [t for t in station_dict if t['owl:sameAs'] == v][0]
            v_name = v_data['dc:title']

            # リンクデータを作成
            link_data = (u_id, v, {
                'link_type': 'transfer',
                'same_station': (u_name == v_name),
                'duration': 5
            })

            transfer_links.append(link_data)

# ----- ネットワークの構築 -----
# グラフの初期化
G = nx.DiGraph()

# エッジの追加
G.add_edges_from(adj_stations_list)
G.add_edges_from(intra_station_links)
G.add_edges_from(transfer_links)

# ノードの追加
G.add_nodes_from(station_nodes)
G.add_nodes_from(type_dir_nodes)

# 最大のものだけ抜粋して保存
G_largest = G.subgraph((max(nx.weakly_connected_components(G), key=len))).copy()
nx.write_gml(G_largest, 'tokyo_graph.gml')

# json形式にして保存
graph_json = nx.node_link_data(G_largest)
with open('tokyo_graph.json', 'w', encoding = 'utf-8') as f:
    json.dump(graph_json, f, ensure_ascii = False)

# 乗り換え駅のみ抽出
G_station_groups = G_largest.edge_subgraph([(u,v) for u,v,d in transfer_links if d['same_station'] == True]).copy()

# 乗換駅以外も追加
G_station_groups.add_nodes_from([n for n in station_nodes if n[0] in G_largest])

station_group_nodes = []
station_group_edges = []

station_group_nodes_dict = {}

# つながっている部分ごとに代表点を作成
for d in nx.weakly_connected_components(G_station_groups):
    # 駅情報の取得
    station_data = {node: G.nodes[node] for node in d}

    # 名前の整理
    station_id = 'stationGroup:' + list(d)[0].split('.')[-1]
    station_name = [dict_data['station_name'] for key, dict_data in station_data.items()][0]
    station_name_en = [dict_data['station_name_en'] for key, dict_data in station_data.items()][0]
    rail_lines = [dict_data['railway'] for key, dict_data in station_data.items()]

    lat_list = [dict_data['y'] for key, dict_data in station_data.items() if 'y' in dict_data]
    lon_list = [dict_data['x'] for key, dict_data in station_data.items() if 'x' in dict_data]

    station_group_nodes_dict[station_name] = {
        'node_type': 'station_group',
        'station_nodes': list(d),
        'station_name': station_name,
        'station_name_en': station_name_en,
        'railway_list': rail_lines
    }

    if len(lat_list) > 0:
        station_group_nodes_dict[station_name]['lat'] = sum(lat_list) / len(lat_list)
        station_group_nodes_dict[station_name]['lon'] = sum(lon_list) / len(lon_list)

    # エッジの追加
    for node in d:
        station_group_edges.append((station_name, node, {
            'link_type': 'station_group',
            'duration': 0,
        }))
        station_group_edges.append((node, station_name, {
            'link_type': 'station_group',
            'duration': 0,
        }))

# 長音記号などを置き換える
def char_replace(text):
    map = {
        'ū': 'u',
        'ō': 'o',
        'Ū': 'U',
        'Ō': 'O',
        '<': '(',
        '>': ')'
    }
    for before, after in map.items():
        text = text.replace(before, after)
    return text
for k, d in station_group_nodes_dict.items():
    d['station_name_en'] = char_replace(d['station_name_en'])

# 重複を解消していく
duplicates = ['Asakusa', 'Iriya', 'Kamonomiya', 'Kasumigaseki', 'Kugahara', 'Kohoku', 'Koya', 'Ogawamachi', 'Oyama', 'Waseda']

id_dict = {
    '浅草': 'Asakusa',
    '浅草（TX）': 'Asakusa_MIR',
    '入谷（東京都）': 'Iriya_Tokyo',
    '入谷（神奈川県）': 'Iriya_Kanagawa',
    '鴨宮': 'Kamonomiya_Kanagawa', # 東海道線
    '加茂宮': 'Kamonomiya_Saitama', # ニューシャトル
    '霞ケ関': 'Kasumigaseki_Tokyo', # 東京メトロ
    '霞ヶ関': 'Kasumigaseki_Saitama', # 東武
    '江北': 'Kohoku_Tokyo', # 舎人ライナー
    '湖北': 'Kohoku_Chiba', # 成田線
    '高野': 'Koya_Tokyo', # 舎人ライナー
    '幸谷': 'Koya_Chiba', # 流鉄
    '久が原': 'Kugahara_Tokyo', # 東急
    '久我原': 'Kugahara_Chiba', # いすみ鉄道
    '小川町（埼玉県）': 'Ogawamachi_Saitama',
    '小川町（東京都）': 'Ogawamachi_Tokyo',
    '大山': 'Oyama_Tokyo', # 東上線（板橋区）
    '小山': 'Oyama_Tochigi',
    '早稲田（都電）': 'Waseda_Toei',
    '早稲田（東京メトロ）': 'Waseda_Metro',
    '押上': 'Oshiage' # (SKYTREE)を取る
}

for k, d in station_group_nodes_dict.items():
    if d['station_name_en'] in duplicates:
        station_group_nodes_dict[k]['unique_id'] = id_dict[d['station_name']]
        
    else:
        station_group_nodes_dict[k]['unique_id'] = d['station_name_en']

# 駅グループデータを保存
with open('tokyo_stations_all.json', 'w', encoding = 'utf-8') as f:
    json.dump(station_group_nodes_dict, f, ensure_ascii = False)

# 駅グループデータをGeoJSONに置き換え
station_group_geojson = {
    'type': 'FeatureCollection',
    'features': []
}

for station_name, station_data in station_group_nodes_dict.items():
    if 'lat' not in station_data:
        continue
    feature = {
        'type': 'Feature',
        'geometry': {
            'coordinates': [station_data['lon'], station_data['lat']],
            'type': 'Point'
        },
        'properties': {}
    }
    for key, value in station_data.items():
        if key in ['lat', 'lon']:
            continue
        feature['properties'][key] = value

    station_group_geojson['features'].append(feature)

# 駅グループデータを保存
with open('tokyo_stations.geojson', 'w', encoding = 'utf-8') as f:
    json.dump(station_group_geojson, f, ensure_ascii = False)

