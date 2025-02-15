# 大都市交通センサスの作成

import os
import pandas as pd
import geopandas as gpd
import pickle
import json
from shapely.geometry import LineString

# ファイルパス
od_path = os.path.join('data', 'transport_census', 'OD調査')

# dfのロード
df_list2 = []
# 乗り換え時間ごとに分けて処理
for a in [15, 30, 60]:
    df_timed = []
    for b in range(1,3):
        df_sub = []
        for c in range(1,8):
            # ファイル名のセット
            fn = f'2ji_{str(a)}_{str(b)}_{str(c)}.csv'
            print(f'Importing {fn}')

            # ヘッダーが1つめのファイルにのみ存在
            if c == 1:
                df = pd.read_csv(os.path.join(od_path, fn))
                df_sub.append(df)
            # ひとつめのファイルからヘッダーをコピー
            else:
                df = pd.read_csv(os.path.join(od_path, fn), header = None)
                df.columns = df_sub[0].columns
                df_sub.append(df)
        
        # dfを合体
        df_sub_concat = pd.concat(df_sub, ignore_index = True)

        # 日付を追加
        df_sub_concat['day'] = b

        # dfを合体させる
        df_timed.append(df_sub_concat)
    
    # dfを合体させる
    df_timed_combined = pd.concat(df_timed, ignore_index = True)

    # インターバル列を作成
    df_timed_combined['max_interval'] = a

    # dfを追加
    df_list2.append(df_timed_combined)

# 列の形式をcategoricalに変更
cat_cols = ['圏域', 'カード種別', '【入場】圏域', '【出場】圏域']
for df in df_list2:
    for c in cat_cols:
        df[c] = df[c].astype('category')

# parquetとして保存
df_list2[0].to_parquet(os.path.join(od_path, '2ji_OD_15.parquet'))
df_list2[1].to_parquet(os.path.join(od_path, '2ji_OD_30.parquet'))
df_list2[2].to_parquet(os.path.join(od_path, '2ji_OD_60.parquet'))

# ----- 経路情報の重み付け -----
# 改めてセンサスのデータを読み取り
od_path = os.path.join('data', 'transport_census', 'OD調査')
od2_15 = pd.read_parquet(os.path.join(od_path, '2ji_OD_15.parquet'))

# 駅データをロード
stations_gdf = gpd.read_file('tokyo_stations_cycles.geojson')
station_list = set(stations_gdf['station_name'])

# 首都圏だけフィルター
od2_15_tokyo = od2_15[od2_15['圏域'] == '1.首都圏'].copy()

# 駅リストを作成
od_station_list = set(od2_15_tokyo['【入場】駅名'].to_list() + od2_15_tokyo['【出場】駅名'].to_list())

# データの修正作業
# 単体で直せるもの
# 駅名の表記揺れ
stations_fix_od2eki = {
    '四ッ谷': '四ツ谷',
    '箱根ヶ崎': '箱根ケ崎',
    '姉ヶ崎': '姉ケ崎',
    '袖ヶ浦': '袖ケ浦',
    '茅ヶ崎': '茅ケ崎',
    '北茅ヶ崎': '北茅ケ崎',
    '保土ヶ谷': '保土ケ谷',
    '阿佐ヶ谷': '阿佐ケ谷',
    '三ッ沢下町': '三ツ沢下町',
    '三ッ沢上町': '三ツ沢上町',
    '千駄ヶ谷': '千駄ケ谷',
    '戸塚': '戸塚', # 微妙に違う
    '笹塚': '笹塚',
    '麹町': '麴町',
    '市ヶ谷': '市ケ谷',
    '鶴ヶ峰': '鶴ケ峰',
    '希望ヶ丘': '希望ケ丘',
    'ＹＲＰ野比': 'YRP野比',
    'モノレール浜松町': '浜松町',
    '二重橋前': '二重橋前〈丸の内〉',
    '明治神宮前': '明治神宮前〈原宿〉',
    'みなみ寄居': 'みなみ寄居<ホンダ寄居前>',
    '獨協大学前': '獨協大学前<草加松原>',
    '花月園前': '花月総持寺',
    '赤坂': '赤坂（東京都）', # 東京の赤坂しかデータがない
    '早稲田': '早稲田（東京メトロ）', # 都電はデータ無し
    '栄町': '栄町（千葉県）', # 都電はデータ無し
    '平和台': '平和台（東京都）', # 流鉄はデータ無し
    '永田': '永田（千葉県）', # 秩父鉄道はデータ無し
}

# create list for type
entry_exit = ['【入場】', '【出場】']
# 単体のものを直していく
for e in entry_exit:
    od2_15_tokyo[f'{e}駅名'] = od2_15_tokyo[f'{e}駅名'].apply(
        lambda x: stations_fix_od2eki[x] if x in stations_fix_od2eki else x
    )

# 区別する必要があるものを分類
stations_fix_operators = {
    '浅草': {
        '首都圏新都市鉄道': '浅草（TX）',
        '東京地下鉄': '浅草',
        '東京都交通局': '浅草',
        '東武鉄道': '浅草'
    },
    '入谷': {
        '東京地下鉄': '入谷（東京都）',
        '東日本旅客鉄道': '入谷（神奈川県）'
    },
    '小川町': {
        '東京都交通局': '小川町（東京都）',
        '東武鉄道': '小川町（埼玉県）',
        '東日本旅客鉄道': '小川町（埼玉県）',
    },
    '豊島園': {
        '西武鉄道': '豊島園（西武）',
        '東京都交通局': '豊島園（都営）',
    },
    '弘明寺': {
        '横浜市交通局': '弘明寺（市営地下鉄）',
        '京浜急行電鉄': '弘明寺（京急）',
    },
}

# dfにする
mapping_df = pd.DataFrame([
    {'station': station, 'operator': operator, 'fixed_name': fixed_name}
    for station, operators in stations_fix_operators.items()
    for operator, fixed_name in operators.items()
])

# 事業者とのあわせ技のものを直していく
for e in entry_exit:
    od2_15_tokyo = od2_15_tokyo.merge(
        mapping_df,
        left_on=[f'{e}駅名', f'{e}事業者名'],
        right_on=['station', 'operator'],
        how='left'
    )
    od2_15_tokyo[f'{e}駅名'] = od2_15_tokyo['fixed_name'].fillna(od2_15_tokyo[f'{e}駅名'])
    od2_15_tokyo.drop(columns=['station', 'operator', 'fixed_name'], inplace=True)

# 人数ごとの集計
passengers_df = od2_15_tokyo.groupby(['【入場】駅名', '【出場】駅名'])['人数'].sum().reset_index()

# OD表の駅名リストを作成
od_station_list = set(od2_15_tokyo['【入場】駅名'].to_list() + od2_15_tokyo['【出場】駅名'].to_list())

# 不要な行を削除
# 同一駅発着、駅が範囲外のものを削除
passengers_df = passengers_df[(passengers_df['【入場】駅名'] != passengers_df['【出場】駅名']) & passengers_df['【入場】駅名'].isin(station_list) & passengers_df['【出場】駅名'].isin(station_list)]

# この状態で保存
fp = os.path.join('data', 'dump')
passengers_df.to_parquet(os.path.join(fp, 'transport_census.parquet'))

# ----- 最短経路と合体 -----

# 最短経路を読み取り
with open(os.path.join(fp, 'nocycle_dist.pkl'), 'rb') as file:
    shortest_dists_nocycle = pickle.load(file)
with open(os.path.join(fp, 'force_cycle_path.pkl'), 'rb') as file:
    shortest_paths = pickle.load(file)
with open(os.path.join(fp, 'force_cycle_dist.pkl'), 'rb') as file:
    shortest_dists = pickle.load(file)

edge_betweenness = {}
node_betweenness = {}

thresholds = range(0,11,5)

lengths = shortest_dists.keys()

for idx, row in passengers_df.iterrows():
    source = row['【入場】駅名']
    target = row['【出場】駅名']
    passengers = row['人数'] / 2 # 2日間のデータであるため1日あたりに補正

    # 経路を取得
    if source not in shortest_dists_nocycle:
        continue
    if target not in shortest_dists_nocycle[source]:
        continue

    for length in lengths:
    
        # チャリで時間がかかりすぎるのは無視
        duration = shortest_dists[length][source][target]

        # 閾値を複数設定
        for threshold in thresholds:

            if shortest_dists_nocycle[source][target] + threshold < duration:
                continue

            path = shortest_paths[length][source][target]

            # 媒介中心性を計算
            for i in range(len(path) - 1):
                if ('cycle_on' in path[i]) and ('cycle_off' in path[i + 1]):
                    c_source = path[i].replace('_cycle_on', '').replace('AC+', '')
                    c_target = path[i + 1].replace('_cycle_off', '').replace('AC+', '')

                    # リンクの媒介中心性を計算
                    # 逆がすでにあればそこに追加
                    if (c_target, c_source) in edge_betweenness:
                        edge_betweenness[(c_target, c_source)][threshold][length] = edge_betweenness[(c_target, c_source)][threshold][length] + passengers

                    # 逆がない場合、元のがなければ新たにデータを生成した後、そこにたしていく
                    else:
                        if (c_source, c_target) not in edge_betweenness:
                            edge_betweenness[(c_source, c_target)] = {t: {l: 0 for l in lengths} for t in thresholds}

                        edge_betweenness[(c_source, c_target)][threshold][length] = edge_betweenness[(c_source, c_target)][threshold][length] + passengers
                    
                    for node in [c_source, c_target]:
                        if node not in node_betweenness:
                            node_betweenness[node] = {t: {l: 0 for l in lengths} for t in thresholds}

                        node_betweenness[node][threshold][length] = node_betweenness[node][threshold][length] + passengers

# リストを初期化
data = []

# 中心性を計算したものを基に足していく
for (source, target), value in edge_betweenness.items():

    if source not in station_list or target not in station_list:
        continue
    
    # 図形を抽出
    source_geom = stations_gdf[stations_gdf['station_name'] == source].geometry.iloc[0]
    target_geom = stations_gdf[stations_gdf['station_name'] == target].geometry.iloc[0]
    line = LineString([source_geom, target_geom])
    
    # データをリストに追加
    data.append({'source': source, 'target': target, 'betweenness': value, 'geometry': line})

# Create a GeoDataFrame
edge_betweenness_gdf = gpd.GeoDataFrame(data, crs=stations_gdf.crs)

# リンクの距離データを追加
edge_betweenness_gdf['length'] = edge_betweenness_gdf.to_crs('EPSG:6677').geometry.length * 1.5
edge_betweenness_gdf_sorted = edge_betweenness_gdf.sort_values(by='length', ascending=False)

with open('tokyo_stations_cycles.geojson', 'r', encoding = 'utf-8') as f:
    stations_dict = json.load(f)

for feature in stations_dict['features']:
    st_name = feature['properties']['station_name']
    if st_name in node_betweenness:
        feature['properties']['betweenness'] = node_betweenness[st_name]
    else:
        feature['properties']['betweenness'] = {t: {l: 0 for l in range(0,11,2)} for t in range(0,11,5)}

# 保存
fp = os.path.join('data', 'dump')
edge_betweenness_gdf.to_file(os.path.join(fp, 'edge_bet.geojson'), driver = 'GeoJSON')

with open(os.path.join(fp, 'tokyo_stations_bet.geojson'), 'w', encoding = 'utf-8') as f:
    json.dump(stations_dict, f, ensure_ascii = False)

