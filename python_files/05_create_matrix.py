# ポテンシャルマップのための最短経路を計算

import networkx as nx
import pandas as pd
import geopandas as gpd
import json
import os
import pickle

# データをロード
G_cycles = nx.read_gml('tokyo_graph_thru.gml')

# ----- 自転車のためのネットワーク構築 -----

# 短いリンクを取り除く（1km以下）
short_edges = [(u, v) for u, v, d in G_cycles.edges(data = True) if d['link_type'] == 'cycle' and d['distance'] < 1000]
G_cycles.remove_edges_from(short_edges)

# 2層目のネットワークを構築
# コピーしてすべてのノードの名前を変える
# AC: after cycle から
mapping = {node: f'AC+{node}' for node in G_cycles.nodes}
G_cycles_copy = nx.relabel_nodes(G_cycles, mapping, copy = True)
G_layered = nx.compose(G_cycles, G_cycles_copy)
# 自転車エッジを抽出、終点を新しい層に接続
additional_edges = [(u,f'AC+{v}',d) for u,v,d in G_cycles.edges(data = True) if d['link_type'] == 'cycle']
G_layered.add_edges_from(additional_edges)
# 保存
nx.write_gml(G_layered, 'tokyo_graph_layered.gml')
# jsonとして保存
graph_json = nx.node_link_data(G_layered)
with open('tokyo_graph_layered.json', 'w', encoding = 'utf-8') as f:
    json.dump(graph_json, f, ensure_ascii = False)

# ----- 最短経路の検索 -----
# 駅データの読み込み
stations_gdf = gpd.read_file('tokyo_stations.geojson')

# 自転車なしのネットワークを構築
G_comp = G_cycles.copy()
cycle_edges = [(u, v) for u, v, d in G_cycles.edges(data = True) if d['link_type'] == 'cycle']
G_comp.remove_edges_from(cycle_edges)

# 最短距離を計算する
# チャリなし

shortest_paths_nocycle = {}
shortest_dists_nocycle = {}

for source in [n for n in G_comp.nodes if 'source' in n]:
    shortest_dist, shortest_path = nx.single_source_dijkstra(G_comp, source = source, weight = 'duration')
    shortest_dists_nocycle[source.replace('_source', '')] = {target.replace('_target', ''): round(shortest_dist[target], 3) for target in shortest_dist if 'target' in target}
    shortest_paths_nocycle[source.replace('_source', '')] = {target.replace('_target', ''): shortest_path[target] for target in shortest_path if 'target' in target}

# チャリありについては、距離に応じて複数パターンを作成
shortest_dists = {}
shortest_paths = {}

# 自転車の最長距離を4,6,8,10の4パターンで計算
for n in range(4, 11, 2):
    print(f'Calculation for maximum cycling distance: {n} km')
    shortest_dists[n] = {}
    shortest_paths[n] = {}
    # 長いエッジを除去
    # 短いのも削除（2km以下）
    G_temp = G_layered.copy()
    long_edges = [(u, v) for u, v, d in G_layered.edges(data = True) if d['link_type'] == 'cycle' and (d['distance'] > n * 1000 or d['distance'] < 2000)]
    G_temp.remove_edges_from(long_edges)

    # 最短距離を計算する
    for source in [n for n in G_temp.nodes if (('source' in n) and ('AC+' not in n))]:
        shortest_dist, shortest_path = nx.single_source_dijkstra(G_temp, source = source, weight = 'duration')
        # 必要な部分だけ抽出、小数第3位までに丸める
        shortest_dists[n][source.replace('_source', '')] = {target.replace('_target', '').replace('AC+', ''): round(shortest_dist[target], 3) for target in shortest_dist if (('target' in target) and ('AC+' in target))}
        shortest_paths[n][source.replace('_source', '')] = {target.replace('_target', '').replace('AC+', ''): shortest_path[target] for target in shortest_path if (('target' in target) and ('AC+' in target))}

print('Done')

# まとめて保存
fp = os.path.join('data', 'dump')
os.makedirs(fp, exist_ok = True)
with open(os.path.join(fp, 'nocycle_path.pkl'), 'wb') as file:
    pickle.dump(shortest_paths_nocycle, file)
with open(os.path.join(fp, 'nocycle_dist.pkl'), 'wb') as file:
    pickle.dump(shortest_dists_nocycle, file)
with open(os.path.join(fp, 'force_cycle_path.pkl'), 'wb') as file:
    pickle.dump(shortest_paths, file)
with open(os.path.join(fp, 'force_cycle_dist.pkl'), 'wb') as file:
    pickle.dump(shortest_dists, file)