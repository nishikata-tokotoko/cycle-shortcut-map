# 自転車データをネットワークに紐づけるのと、H3グリッドの導入

import pandas as pd
import geopandas as gpd
import json
import h3
import os
import matplotlib.pyplot as plt

# パラメーターの設定
h3_res = 11
k = 7

# GBFSデータの読み込み
gbfs_fp = os.path.join('..', 'data_prep', 'data', 'gbfs')
docomo_ports = gpd.read_file(os.path.join(gbfs_fp, 'docomo-cycle', 'station_information.geojson'))
hello_ports = gpd.read_file(os.path.join(gbfs_fp, 'hellocycling', 'station_information.geojson'))

# H3 index
hello_ports['h3_index'] = hello_ports['geometry'].apply(
    lambda coords: h3.latlng_to_cell(coords.y, coords.x, h3_res)
)
docomo_ports['h3_index'] = docomo_ports['geometry'].apply(
    lambda coords: h3.latlng_to_cell(coords.y, coords.x, h3_res)
)

hello_counts = hello_ports.groupby('h3_index')['station_id'].count()
hello_counts.name = 'hello_count'
docomo_counts = docomo_ports.groupby('h3_index')['station_id'].count()
docomo_counts.name = 'docomo_count'

# JSONにて作業
with open('tokyo_stations.geojson', 'r', encoding = 'utf-8') as f:
    stations_dict = json.load(f)

for feature in stations_dict['features']:
    coords = feature['geometry']['coordinates']
    h3_index = h3.latlng_to_cell(coords[1], coords[0], h3_res)
    feature['properties']['h3_index'] = h3_index
    hello = int(sum([hello_counts[h] for h in h3.grid_disk(h3_index, k) if h in hello_counts.index]))
    docomo = int(sum([docomo_counts[h] for h in h3.grid_disk(h3_index, k) if h in docomo_counts.index]))

    feature['properties']['helloPortCounts'] = hello
    feature['properties']['docomoPortCounts'] = docomo
    feature['properties']['totalPortCounts'] = hello + docomo

# 駅グループデータを保存
with open('tokyo_stations_cycles.geojson', 'w', encoding = 'utf-8') as f:
    json.dump(stations_dict, f, ensure_ascii = False)

# サイクルポートのデータを保存
docomo_ports.to_file('docomo_ports.geojson', driver = 'GeoJSON', encoding = 'utf-8')
hello_ports.to_file('hello_ports.geojson', driver = 'GeoJSON', encoding = 'utf-8')