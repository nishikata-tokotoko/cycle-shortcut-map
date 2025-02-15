# 自転車による移動の追加

import networkx as nx
import pandas as pd
import geopandas as gpd
import itertools
import json
import os
from scipy.spatial.distance import cdist

# load file
G = nx.read_gml('tokyo_graph.gml')
tokyo_stations = gpd.read_file('tokyo_stations.geojson')

# 平面直角座標系IV系
tokyo_stations_reproj = tokyo_stations.to_crs('EPSG:6677')

# 駅データの追加
station_nodes = []
source_target_nodes = []
source_target_edges = []

for idx, row in tokyo_stations.iterrows():
    station_name = row['station_name']
    # 乗車ノード
    on_node_data = (station_name + '_on', {
        'node_type': 'station_group_on',
        'station_name': row['station_name'],
        'station_nodes': row['station_nodes'],
        'railways': row['railway_list'],
        'x': row['geometry'].x,
        'y': row['geometry'].y
    })
    
    # 降車ノード
    off_node_data = (station_name + '_off', {
        'node_type': 'station_group_on',
        'station_name': row['station_name'],
        'station_nodes': row['station_nodes'],
        'railways': row['railway_list'],
        'x': row['geometry'].x,
        'y': row['geometry'].y
    })

    station_nodes.append(on_node_data)
    station_nodes.append(off_node_data)

    # 出発地点ノード
    source_node_data = (station_name + '_source', {
        'node_type': 'station_source',
        'station_name': station_name,
        'x': row['geometry'].x,
        'y': row['geometry'].y        
    })

    # 到着地点ノード
    target_node_data = (station_name + '_target', {
        'node_type': 'station_target',
        'station_name': station_name,
        'x': row['geometry'].x,
        'y': row['geometry'].y
    })

    source_target_nodes.append(source_node_data)
    source_target_nodes.append(target_node_data)

    for d in ['on', 'off']:
        source_edge = (station_name + '_source', station_name + f'_{d}', {
            'link_type': 'source',
            'duration': 0.001
        })
        target_edge = (station_name + f'_{d}', station_name + f'_target', {
            'link_type': 'target',
            'duration': 0.001
        })
        source_target_edges.append(source_edge)
        source_target_edges.append(target_edge)

# 駅間距離を計算
station_names = tokyo_stations_reproj['station_name'].tolist()
coords = tokyo_stations_reproj['geometry'].apply(lambda geom: (geom.x, geom.y)).tolist()
# Compute pairwise distances
distances = cdist(coords, coords)

# Create a DataFrame with source, target, and distance
distance_data = []
for i, j in itertools.permutations(range(len(station_names)), 2):
    distance_data.append({
        'source': station_names[i],
        'target': station_names[j],
        'distance': distances[i][j]
    })

# dfに保存
distance_df = pd.DataFrame(distance_data)

# 速度の設定
walk_speed = 80
cycle_speed = 250

# 道のりは直線距離の1.5倍
dist_factor = 1.5

distance_df['distance_calib'] = distance_df['distance'] * dist_factor
distance_df['walk_duration'] = distance_df['distance_calib'] / walk_speed
distance_df['cycle_duration'] = distance_df['distance_calib'] / cycle_speed

# これをリンクとして追加
walk_edgelist = []
cycle_edgelist = []

for idx, row in distance_df.iterrows():
    source = row['source']
    target = row['target']
    dist = row['distance_calib']

    # 徒歩リンク
    if dist < 4000:
        walk_edgelist.append((
            source + '_off', target + '_on', {
                'link_type': 'walk',
                'duration': row['walk_duration'],
                'distance': dist
            }
        ))

    # 自転車リンク
    if dist < 10000:
        cycle_edgelist.append((
            source + '_cycle_on', target + '_cycle_off', {
                'link_type': 'cycle',
                'duration': row['cycle_duration'],
                'distance': dist
            }
        ))

# ----- 自転車の乗降ノードの処理 -----
# 自転車の乗降については、以下の要素を追加で作成
# 乗車ノード
# 降車ノード
# 接続リンク
cycle_station_links = []
cycle_nodes = []

for idx, row in tokyo_stations.iterrows():
    # 駅・自転車のノード
    cycle_on_node = (row['station_name'] + '_cycle_on', {
        'node_type': 'cycle_on',
        'station_name': row['station_name'],
        'has_hellocycling': True,
        'has_docomo': True,
        'x': row['geometry'].x,
        'y': row['geometry'].y
    })
    cycle_off_node = (row['station_name'] + '_cycle_off', {
        'node_type': 'cycle_off',
        'station_name': row['station_name'],
        'has_hellocycling': True,
        'has_docomo': True,
        'x': row['geometry'].x,
        'y': row['geometry'].y
    })
    cycle_nodes.append(cycle_on_node)
    cycle_nodes.append(cycle_off_node)

    # 駅・自転車間のリンク
    duration_data = {
        'link_type': 'cycle_station',
        'duration': 5
    }
    cycle_station_links.append((
        row['station_name'] + '_off', row['station_name'] + '_cycle_on', duration_data
    ))
    cycle_station_links.append((
        row['station_name'] + '_cycle_off', row['station_name'] + '_on', duration_data
    ))

# 駅内リンクの作成
connection_edges = []

# 駅グループから各路線へのリンク
# 乗車と降車について別途作成
for idx, row in tokyo_stations_reproj.iterrows():
    for node in row['station_nodes']:
        duration_data = {
            'link_type': 'connection',
            'duration': 0.01
        }
        connection_edges.append((row['station_name'] + '_on', node, duration_data)) 
        connection_edges.append((node, row['station_name'] + '_off', duration_data))

# すべてのリンクを本のネットワークに追加
# 全部のリンクの追加
G_walk = G.copy()

G_walk.add_edges_from(connection_edges)
G_walk.add_edges_from(walk_edgelist)
G_walk.add_edges_from(source_target_edges)
G_walk.add_nodes_from(station_nodes)
G_walk.add_nodes_from(source_target_nodes)

# 自転車用の追加情報
G_cycles = G_walk.copy()

G_cycles.add_edges_from(cycle_station_links)
G_cycles.add_edges_from(cycle_edgelist)
G_cycles.add_nodes_from(cycle_nodes)

# 保存
nx.write_gml(G_cycles, 'tokyo_graph_cycle.gml')
nx.write_gml(G_walk, 'tokyo_graph_comp.gml')

# ----- 直通運転処理 -----
# 相互直通
stations_list_diff = ['大崎', '羽沢横浜国大', '新横浜', '小田原', '中野', '西船橋', '代々木上原', '綾瀬', '赤羽岩淵', '目黒', '渋谷', '和光市', '小竹向原', '北千住', '押上', '泉岳寺', '新宿', '横浜', '東成田', '京成高砂']
# 支線直通（同一会社）
# 品川はエアポート快特のみ、飯能は特急のみ
stations_list_same = ['品川', '京急蒲田', '金沢八景', '堀ノ内', '日吉', '新百合ヶ丘', '相模大野', '調布', '北野', '小平', '萩山', '練馬', '西所沢', '吾野', '曳舟', '新栃木', '下今市', '東武動物公園', '東小泉', '館林', '青砥', '京成高砂', '千葉中央', '京成成田', '取手', '我孫子', '東京', '立川', '拝島', '佐倉', '成田']
stations_list_same = ['品川', '西谷', '二俣川', '小平', '萩山', '練馬', '西所沢', '吾野', '飯能', '笹塚', '我孫子', '西船橋', '東京', '立川', '拝島', '佐倉', '成田']

potential_thru = {
    'station_name': [],
    'link_type': [],
    'source_id': [],
    'target_id': [],
    'source_rail': [],
    'target_rail': [],
    'source_direction': [],
    'target_direction': [],
    'source_type': [],
    'target_type': [],
    'duration': [], 
}

for s in stations_list_diff:
    station_train_nodes = [n for n in G_cycles.nodes(data = True) if ('node_type' in n[1]) and (n[1]['node_type'] == 'train_node') and n[1]['station_name'] == s]
    print(f'{s}, {len(station_train_nodes)}')
    for i,j in itertools.permutations(station_train_nodes, 2):
        i_op = i[1]['railway'].split(':')[1].split('.')[0]
        j_op = j[1]['railway'].split(':')[1].split('.')[0]

        # 違う路線のみ
        if i_op == j_op:
            continue
        potential_thru['station_name'].append(s)
        potential_thru['link_type'].append('thru_service')
        potential_thru['source_id'].append(i[0])
        potential_thru['target_id'].append(j[0])
        potential_thru['source_rail'].append(i[1]['railway'])
        potential_thru['target_rail'].append(j[1]['railway'])
        potential_thru['source_direction'].append(i[1]['direction'])
        potential_thru['target_direction'].append(j[1]['direction'])
        potential_thru['source_type'].append(i[1]['train_type'])
        potential_thru['target_type'].append(j[1]['train_type'])
        potential_thru['duration'].append(99)

for s in stations_list_same:
    station_train_nodes = [n for n in G_cycles.nodes(data = True) if ('node_type' in n[1]) and (n[1]['node_type'] == 'train_node') and n[1]['station_name'] == s]
    print(f'{s}, {len(station_train_nodes)}')
    for i,j in itertools.permutations(station_train_nodes, 2):
        i_op = i[1]['railway'].split(':')[1].split('.')[0]
        j_op = j[1]['railway'].split(':')[1].split('.')[0]

        # 同一社局の違う路線のみ
        if i_op != j_op:
            continue
        if i[1]['railway'] == j[1]['railway']:
            continue
        potential_thru['station_name'].append(s)
        potential_thru['link_type'].append('thru_service')
        potential_thru['source_id'].append(i[0])
        potential_thru['target_id'].append(j[0])
        potential_thru['source_rail'].append(i[1]['railway'])
        potential_thru['target_rail'].append(j[1]['railway'])
        potential_thru['source_direction'].append(i[1]['direction'])
        potential_thru['target_direction'].append(j[1]['direction'])
        potential_thru['source_type'].append(i[1]['train_type'])
        potential_thru['target_type'].append(j[1]['train_type'])
        potential_thru['duration'].append(99)

# 保存
pd.DataFrame(potential_thru).to_csv('potential_thru_add.csv', encoding='cp932')

# ----- 乗り換え時間処理 -----
# 編集した路線データを入れる
edit_fp = os.path.join('..', 'data', 'ksj', 'edit')
with open(os.path.join(edit_fp, 'railway_data.json'), 'r') as f:
    railway_data_dict = json.load(f)

# 初期化
edge_data = []

# mapするためのdictを作成
railway_info = {item['railway_id']: (item['operator_name']['ja'], item['railway_name']['ja']) for item in railway_data_dict}

for u, v, d in G_cycles.edges(data=True):

    if d['link_type'] != 'transfer':
        continue
    # ノードのデータを取得
    source_data = G_cycles.nodes[u]
    target_data = G_cycles.nodes[v]
    
    # 鉄道データを取得
    source_railway = source_data.get('railway', None)
    target_railway = target_data.get('railway', None)
    source_operator_name, source_railway_name = railway_info.get(source_railway, (None, None))
    target_operator_name, target_railway_name = railway_info.get(target_railway, (None, None))
    
    # エッジのデータを保存するdictを作成
    edge_info = {
        'source': u,
        'target': v,
        'link_type': d.get('link_type', None),
        'duration': d.get('duration', None),
        'source_station_name': source_data.get('station_name', None),
        'source_railway': source_railway,
        'source_operator_name': source_operator_name,
        'source_railway_name': source_railway_name,
        'target_station_name': target_data.get('station_name', None),
        'target_railway': target_railway,
        'target_operator_name': target_operator_name,
        'target_railway_name': target_railway_name
    }
    
    # dictをリストに追加
    edge_data.append(edge_info)

# dfを作成
transfer_edges_df = pd.DataFrame(edge_data)

# 編集用CSVを保存
transfer_edges_df.sort_values('source_station_name').to_csv('transfer_edges.csv', encoding = 'cp932')

# ----- 編集したものを読み込み -----

# 乗り換え用
transfer_fp = os.path.join('..', 'data', 'odpt_api', 'transfers')
transfer_edges_df_edited = pd.read_csv(os.path.join(transfer_fp, 'transfer_edges_edited.csv'), encoding = 'cp932') 

# リンクの長さを置き換え
for idx, row in transfer_edges_df_edited.iterrows():
    source = row['source']
    target = row['target']
    duration = row['duration']
    
    if G_cycles.has_edge(source, target):
        G_cycles[source][target]['duration'] = duration

# 直通リンクを読み込む
thru_service = pd.read_csv(os.path.join(transfer_fp, 'potential_thru_edited.csv'), encoding = 'cp932')

# 行ごとに処理
thru_links = []
for idx, row in thru_service.iterrows():
    edge = (
        row['source_id'], 
        row['target_id'], 
        {
            'link_type': row['link_type'],
            'duration': row['duration'],
        }
    )
    thru_links.append(edge)

G_cycles.add_edges_from(thru_links)

# 保存
nx.write_gml(G_cycles, 'tokyo_graph_thru.gml')