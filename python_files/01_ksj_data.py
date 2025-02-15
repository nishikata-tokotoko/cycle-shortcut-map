# 国土数値情報からの補完

import pandas as pd
import geopandas as gpd
import os
import json
import networkx as nx
import shapely
import re
import pykakasi
import copy

# 測地系の設定：平面直角座標系IX系
crs = 'EPSG:6677'

# ODPTのデータをロード
path_odpt = os.path.join('..', 'data', 'odpt_api', 'challenge')
with open(os.path.join(path_odpt, 'Station.json'), 'r') as f:
    station_dict = json.load(f)
with open(os.path.join(path_odpt, 'Operator.json'), 'r') as f:
    operator_dict = json.load(f)
with open(os.path.join(path_odpt, 'Railway.json'), 'r') as f:
    railway_dict = json.load(f)

# dfに置き換え
operator_df = pd.DataFrame.from_dict(operator_dict)
railway_df = pd.DataFrame.from_dict(railway_dict)
station_df = pd.DataFrame.from_dict(station_dict)

railway_df_merged = railway_df.iloc[:,4:].rename(columns = {'owl:sameAs': 'odpt:railway', 'dc:title': 'railwayTitle'}).merge(
    operator_df[['owl:sameAs', 'dc:title', 'odpt:operatorTitle']].copy().rename(columns = {'owl:sameAs': 'odpt:operator', 'dc:title': 'operatorTitle'}),
    on = 'odpt:operator',
    how = 'left'
)

# 国土数値情報のデータを用いて補完

path_ksj = os.path.join('..', 'data', 'ksj', 'N05-23_GML')

# データのロード
stations_ksj = gpd.read_file(os.path.join(path_ksj, 'N05-23_Station2.shp'))
rail_routes_ksj = gpd.read_file(os.path.join(path_ksj, 'N05-23_RailroadSection2.shp'))

# 年号データを整数値に変換
years = ['N05_004', 'N05_005b', 'N05_005e']
for y in years:
    stations_ksj[y] = stations_ksj[y].astype(int)
    rail_routes_ksj[y] = rail_routes_ksj[y].astype(int)

# 現在運行中のデータを抽出
rail_routes_ksj = rail_routes_ksj[rail_routes_ksj['N05_005e'] > 2023].copy()
stations_ksj = stations_ksj[stations_ksj['N05_005e'] > 2023].copy()

# 座標を追加
stations_ksj['x'] = stations_ksj['geometry'].x
stations_ksj['y'] = stations_ksj['geometry'].y

rail_routes_ksj = rail_routes_ksj.to_crs(crs)
stations_ksj = stations_ksj.to_crs(crs)

# 関東圏の事業者のみを抽出

# 元のデータはGADMからダウンロード
japan_geom = gpd.read_file(os.path.join('..', 'data', 'geometry', 'gadm41_JPN_1.json')).to_crs(crs)

kanto_pref = ['Tokyo', 'Saitama', 'Chiba', 'Kanagawa', 'Gunma', 'Tochigi', 'Ibaraki']
kanto_geom = japan_geom[japan_geom['NAME_1'].isin(kanto_pref)].unary_union

# 関東を走る事業者を抽出
kanto_rails = list(rail_routes_ksj[rail_routes_ksj.intersects(kanto_geom)]['N05_003'].unique())

# ケーブルカーの類は落としていく
for r in ['御岳登山鉄道', '高尾登山電鉄', '大山観光電鉄', '筑波観光鉄道']:
    kanto_rails.remove(r)

# JRは一旦除く
kanto_rails_private = kanto_rails.copy()
kanto_rails_private.remove('東日本旅客鉄道（旧国鉄）')
kanto_rails_private.remove('東海旅客鉄道（旧国鉄）')

# 路線の抽出
# JRは1都6県の範囲内に含まれる路線（新幹線は除く）
# それ以外は1都6県に路線を持つ事業者の一覧
jr_routes = rail_routes_ksj[rail_routes_ksj.intersects(kanto_geom) & (rail_routes_ksj['N05_003'] == '東日本旅客鉄道（旧国鉄）') & ~rail_routes_ksj['N05_002'].str.contains('新幹線')].copy()
private_routes = rail_routes_ksj[rail_routes_ksj['N05_003'].isin(kanto_rails_private)].copy()

# 駅も同様
jr_stations = stations_ksj[stations_ksj['N05_002'].isin(jr_routes['N05_002'].unique())].copy()
private_stations = stations_ksj[stations_ksj['N05_003'].isin(kanto_rails_private)].copy()

# ----- 無いデータを補完する -----

# 国土数値情報をODPTデータに合わせる
operator_fix_dict = {
    '東京都': '東京都交通局',
    '横浜市': '横浜市交通局',
    '東京地下鉄': '東京メトロ',
    '京浜急行電鉄': '京急電鉄',
    '銚子電気鉄道': '銚子電鉄',
    '上毛電気鉄道': '上毛電鉄',
    '小湊鐵道': '小湊鉄道株式会社',
    '箱根登山鉄道': '小田急箱根',
}

private_routes['N05_003'] = private_routes['N05_003'].apply(lambda x: operator_fix_dict[x] if x in operator_fix_dict else x)
private_stations['N05_003'] = private_stations['N05_003'].apply(lambda x: operator_fix_dict[x] if x in operator_fix_dict else x)

operator_dict_edit = operator_dict.copy()

# データが無い路線を追加
operator_dict_edit = operator_dict_edit + [
    {   
        '@type': 'odpt:Operator',
        'dc:title': '山万',
        'owl:sameAs': 'odpt.Operator:Yamaman',
        'odpt:operatorTitle': {'en': 'Yamaman', 'ja': '山万'}
    }, 
    {
        'dc:title': '真岡鐵道',
        'owl:sameAs': 'odpt.Operator:Moka',
        'odpt:operatorTitle': {'en': 'Moka Railway', 'ja': '真岡鐵道'}
    }
]

# 路線名を追記
private_routes['N05_002'] = private_routes.apply(
    lambda row: re.sub(r'\d*号線', '', row['N05_002']) if row['N05_003'] in ['東京メトロ', '東京都交通局'] else row['N05_002'],
    axis = 1
)
private_stations['N05_002'] = private_stations.apply(
    lambda row: re.sub(r'\d*号線', '', row['N05_002']) if row['N05_003'] in ['東京メトロ', '東京都交通局'] else row['N05_002'],
    axis = 1
)

# ODPTにデータが無い路線を抽出
rail_merge_temp = private_routes.rename(columns = {'N05_003': 'operatorTitle', 'N05_002': 'railwayTitle'}).merge(
    railway_df_merged,
    on = ['operatorTitle', 'railwayTitle'],
    how = 'left'
)

# 国土数値情報の路線名をODPTに合わせる
railway_fix_dict = {
    '京成電鉄': {
        '本線': '京成本線',
        '成田空港線': '成田スカイアクセス線'
    },
    '京急電鉄': {
        '本線': '京急本線'
    },
    '東武鉄道': {
        '野田線': '東武アーバンパークライン', 
        '東上本線': '東上線'  
    },
    '小湊鉄道株式会社': {
        '小湊鐵道線': '小湊鉄道線',
    },
    '銚子電鉄': {
        '銚子電気鉄道線': '銚子電鉄線'
    },
    '埼玉新都市交通': {
        '伊奈線': 'ニューシャトル',
    },
    '千葉都市モノレール': {
        '1号線': '１号線',
        '2号線': '２号線'
    },
    '首都圏新都市鉄道': {
        '常磐新線': 'つくばエクスプレス'
    },
    '横浜高速鉄道': {
        'みなとみらい21線': 'みなとみらい線'
    },
    '多摩都市モノレール': {
        '多摩都市モノレール線': '多摩モノレール'
    },
    '横浜市交通局': {
        '1号線': 'ブルーライン',
        '3号線': 'ブルーライン',
        '4号線': 'グリーンライン'
    },
    'ゆりかもめ': {
        '東京臨海新交通臨海線': 'ゆりかもめ'
    },
    '東京都交通局': {
        '荒川線': '東京さくらトラム（都電荒川線）'
    },
    '東京メトロ': {
        '丸ノ内線分岐線': '丸ノ内線支線'
    },
    '東京臨海高速鉄道': {
        '臨海副都心線': 'りんかい線'
    },
    '宇都宮ライトレール': {
        '宇都宮芳賀ライトレール線': '宇都宮ライトレール'
    },
    '東京モノレール': {
        '東京モノレール羽田線': '羽田空港線'
    },
    '相模鉄道': {
        '相鉄いずみ野線': 'いずみ野線'
    },
    '湘南モノレール': {
        '江の島線': '湘南モノレール線'
    },
    '小田急箱根': {
        '鉄道線': '箱根登山線',
        '鋼索線': '箱根登山ケーブルカー'
    }
}

private_routes['N05_002'] = private_routes.apply(
    lambda row: railway_fix_dict[row['N05_003']][row['N05_002']] if (row['N05_003'] in railway_fix_dict and row['N05_002'] in railway_fix_dict[row['N05_003']]) else row['N05_002'],
    axis = 1
)

private_stations['N05_002'] = private_stations.apply(
    lambda row: railway_fix_dict[row['N05_003']][row['N05_002']] if (row['N05_003'] in railway_fix_dict and row['N05_002'] in railway_fix_dict[row['N05_003']]) else row['N05_002'],
    axis = 1
)

# 無い路線
rail_merge_temp = private_routes.rename(columns = {'N05_003': 'operatorTitle', 'N05_002': 'railwayTitle'}).merge(
    railway_df_merged,
    on = ['operatorTitle', 'railwayTitle'],
    how = 'left'
)

# 追加する路線
# 京成千原線、ユーカリが丘線、真岡鐵道真岡線、箱根登山ケーブルカー
railway_dict_edit = railway_dict + [
    {
        '@type': 'odpt:Railway',
        'dc:title': '千原線',
        'owl:sameAs': 'odpt.Railway:Keisei.Chihara',
        'odpt:operator': 'odpt.Operator:Keisei',
        'odpt:railwayTitle': {'en': 'Chihara Line', 'ja': '千原線'},
        'odpt:stationOrder': []
    },
    {
        '@type': 'odpt:Railway',
        'dc:title': 'ユーカリが丘線',
        'owl:sameAs': 'odpt.Railway:Yamaman.Yukarigaoka',
        'odpt:operator': 'odpt.Operator:Yamaman',
        'odpt:railwayTitle': {'en': 'Yukarigaoka Line', 'ja': 'ユーカリが丘線'},
        'odpt:stationOrder': []
    },
    {
        '@type': 'odpt:Railway',
        'dc:title': '真岡線',
        'owl:sameAs': 'odpt.Railway:Moka.Moka',
        'odpt:operator': 'odpt.Operator:Moka',
        'odpt:railwayTitle': {'en': 'Moka Line', 'ja': '真岡線'},
        'odpt:stationOrder': []
    },
    {
        '@type': 'odpt:Railway',
        'dc:title': '箱根登山ケーブルカー',
        'owl:sameAs': 'odpt.Railway:OdakyuHakone.Cablecar',
        'odpt:operator': 'odpt.Operator:OdakyuHakone',
        'odpt:railwayTitle': {'en': 'Hakone-Tozan Cablecar', 'ja': '箱根登山ケーブルカー'},
        'odpt:stationOrder': []
    }
]

operator_df_edit = pd.DataFrame.from_dict(operator_dict_edit)
railway_df_edit = pd.DataFrame.from_dict(railway_dict_edit)

railway_df_merged_edit = railway_df_edit.iloc[:,4:].rename(columns = {'owl:sameAs': 'odpt:railway', 'dc:title': 'railwayTitle'}).merge(
    operator_df_edit[['owl:sameAs', 'dc:title', 'odpt:operatorTitle']].copy().rename(columns = {'owl:sameAs': 'odpt:operator', 'dc:title': 'operatorTitle'}),
    on = 'odpt:operator',
    how = 'left'
)

# 無い路線がなくなったことを確認
rail_merge_temp = private_routes.rename(columns = {'N05_003': 'operatorTitle', 'N05_002': 'railwayTitle'}).merge(
    railway_df_merged_edit,
    on = ['operatorTitle', 'railwayTitle'],
    how = 'left'
)

# 駅名の修正
# 同様に、国土数値情報をODPTデータに合わせていく
station_fix_dict = {
    '東京モノレール': {
        'モノレール浜松町': '浜松町',
        '羽田空港第1ターミナル': '羽田空港第１ターミナル',
        '羽田空港第2ターミナル': '羽田空港第２ターミナル',
        '羽田空港第3ターミナル': '羽田空港第３ターミナル',   
    },
    '京成電鉄': {
        '空港第2ビル': '空港第２ビル'
    },
    '京急電鉄': {
        '羽田空港第1・第2ターミナル': '羽田空港第１・第２ターミナル',
        '羽田空港第3ターミナル': '羽田空港第３ターミナル',   
    },
    '舞浜リゾートライン': {
        'リゾートゲートウェイ･ステーション': 'リゾートゲートウェイ・ステーション'
    }
}

private_stations['N05_011'] = private_stations.apply(
    lambda row: station_fix_dict[row['N05_003']][row['N05_011']] if (row['N05_003'] in station_fix_dict and row['N05_011'] in station_fix_dict[row['N05_003']]) else row['N05_011'],
    axis = 1
)

# 国土数値情報のデータにODPTのIDをマージ
private_stations_merge = private_stations.rename(columns = {'N05_003': 'operatorTitle', 'N05_002': 'railwayTitle'}).merge(
    rail_merge_temp.groupby(['railwayTitle', 'operatorTitle'])[['odpt:railway', 'odpt:operator']].first().reset_index(),
    on = ['operatorTitle', 'railwayTitle'],
    how = 'left'
)

# 国土数値情報の駅のうち、ODPTにデータがない駅を抽出
missing_station_df = private_stations_merge.rename(columns = {'N05_011': 'dc:title'}).merge(
    station_df.iloc[:, 3:],
    on = ['odpt:operator', 'odpt:railway', 'dc:title'],
    how = 'left'
).sort_values(by = ['operatorTitle', 'railwayTitle', 'N05_006'])

# ふりがなを作成
kakasi = pykakasi.kakasi()
def romanize_kakasi(text):
    result = '-'.join([r['passport'].title() for r in kakasi.convert(text)])
    return result
missing_station_df['romaji'] = missing_station_df['dc:title'].apply(romanize_kakasi)

# ない駅を保存
# すでにデータが有る路線（不整合があったもの）は削除
# ふりがなと接続駅データを作成
missing_station_df[
    missing_station_df['owl:sameAs'].isna() & ~missing_station_df['operatorTitle'].str.contains('|'.join(['東京メトロ', '東武鉄道', '東急電鉄', '相模鉄道', '京王電鉄']))
].sort_values(by = ['operatorTitle', 'railwayTitle', 'N05_006']).to_csv(os.path.join('..', 'data', 'ksj', 'missing_stations.csv'), encoding = 'cp932', index = False)

# 行き先あるいは乗換駅としてだけ登録されている駅
# 乗換駅データが存在していない可能性がある
incomplete_stations = station_df[station_df['geo:long'].isna()].sort_values(by = ['odpt:railway'])

incomplete_stations = incomplete_stations.merge(
    private_stations_merge.rename(columns = {'N05_011': 'dc:title'}),
    on = ['odpt:operator', 'odpt:railway', 'dc:title'],
    how = 'inner'    
)

# 座標データを追加
incomplete_stations['geo:lat'] = incomplete_stations['y']
incomplete_stations['geo:long'] = incomplete_stations['x']

# データを保存
incomplete_stations.to_csv(os.path.join('..', 'data', 'ksj', 'incomplete_stations.csv'), encoding = 'cp932', index = False)

# このデータをCSV上で適宜編集する

# 編集したデータを読み込む
missing_df_annotated = pd.read_csv(os.path.join('..', 'data', 'ksj', 'missing_stations_edit.csv'), encoding = 'cp932')
incomplete_stations_annotated = pd.read_csv(os.path.join('..', 'data', 'ksj', 'incomplete_stations.csv'), encoding = 'cp932')

# 追加する事業者をここで選ぶ
additional_operators = ['京成電鉄', '北総鉄道', '新京成電鉄', '芝山鉄道', '山万', '埼玉高速鉄道', '東京モノレール', '東葉高速鉄道', '横浜高速鉄道', '鹿島臨海鉄道', '江ノ島電鉄', '湘南モノレール', '舞浜リゾートライン', 'いすみ鉄道', 'ひたちなか海浜鉄道', '千葉都市モノレール', '小湊鉄道株式会社', '横浜シーサイドライン', '流鉄']

additional_operators = missing_df_annotated['operatorTitle'].unique()

missing_df_annotated = missing_df_annotated[missing_df_annotated['operatorTitle'].apply(lambda x: x in additional_operators)].copy()
incomplete_stations_annotated = incomplete_stations_annotated[incomplete_stations_annotated['operatorTitle'].apply(lambda x: x in additional_operators)].copy()

# 入力情報を基に追記
missing_df_annotated['owl:sameAs'] = missing_df_annotated['odpt:railway'].str.replace('odpt.Railway:', 'odpt.Station:') + '.' + missing_df_annotated['romaji'].str.replace('-', '')
missing_df_annotated['odpt:stationTitle'] = missing_df_annotated.apply(
    lambda row: {'en': row['romaji'], 'ja': row['dc:title']},
    axis = 1
)
missing_df_annotated['geo:lat'] = missing_df_annotated['y']
missing_df_annotated['geo:long'] = missing_df_annotated['x']

# 接続駅情報を追加
def get_connecting(row):
    st_id = row['owl:sameAs']
    railway_temp = row['odpt:railway']

    connecting_railway = []
    connecting_station = []
    
    # dfをループして自身が含まれている駅を抽出
    for i, r in station_df.iterrows():
        cs_temp = r['odpt:connectingStation']
        cr_temp = r['odpt:connectingRailway']
        
        if not isinstance(cs_temp, list):
            continue

        # 発見したら駅情報を追加
        if st_id in cs_temp:
            connecting_railway += cr_temp
            connecting_station += cs_temp

            connecting_railway.append(r['odpt:railway'])
            connecting_station.append(r['owl:sameAs'])

    # 重複を削除
    connecting_railway = list(set(connecting_railway))
    connecting_station = list(set(connecting_station))

    if len(connecting_railway) >= 1:
        connecting_station.remove(st_id)
        connecting_railway.remove(railway_temp)

        # 並び替え - 対応するように
        connecting_station.sort()
        connecting_railway.sort()

    else:
        connecting_station = float('nan')
        connecting_railway = float('nan')

    return connecting_station, connecting_railway

incomplete_stations_annotated[['odpt:connectingStation', 'odpt:connectingRailway']] = incomplete_stations_annotated.apply(get_connecting, axis = 1, result_type = 'expand')

# 乗換駅情報を追加
# これらのふたつのdf内での駅のみ追加すれば良い（はず）

# 乗換駅のリスト
# 今後駅が違う場合でも対応できるようにそれぞれリスト化
transfer_stations_list = [
    ['青砥'],
    ['京成高砂'],
    ['京成津田沼'],
    ['千葉中央'],
    ['勝田台', '東葉勝田台'],
    ['ユーカリが丘'],
    ['東成田'],
    ['千葉ニュータウン中央'],
    ['印旛日本医大'],
    ['北習志野'],
    ['上総中野'],
    ['強羅'],
    ['下館'],
    ['桐生', '西桐生'],
    
]

# それぞれ乗り換えリストを作成
for st_list in transfer_stations_list:
    connecting_railway = []
    connecting_station = []

    # それぞれのdfから接続駅情報を追記
    dfs = [missing_df_annotated, incomplete_stations_annotated]
    for df in dfs:
        df_temp = df[df['dc:title'].apply(lambda x: x in st_list)]
        connecting_railway = connecting_railway + df_temp['odpt:railway'].to_list()
        connecting_station = connecting_station + df_temp['owl:sameAs'].to_list()
    
    # 重複を削除
    connecting_railway = list(set(connecting_railway))
    connecting_station = list(set(connecting_station))

    # もし複数路線乗り入れている場合は、それぞれに情報を追記する
    if len(connecting_station) >= 2:
        for df in dfs:
            # 列をfloatからobjectに変更しておく
            df['odpt:connectingRailway'] = df['odpt:connectingRailway'].astype(object)
            df['odpt:connectingStation'] = df['odpt:connectingStation'].astype(object)
            for idx, row in df.iterrows():
                if row['dc:title'] in st_list:
                    cr_temp = connecting_railway.copy()
                    cs_temp = connecting_station.copy()
                    cr_temp.remove(row['odpt:railway'])
                    cs_temp.remove(row['owl:sameAs'])
                    # 念のためリストにする
                    if not isinstance(cr_temp, list):
                        cr_temp = [cr_temp]
                    if not isinstance(cs_temp, list):
                        cs_temp = [cs_temp]
                    df.at[idx, 'odpt:connectingRailway'] = cr_temp
                    df.at[idx, 'odpt:connectingStation'] = cs_temp

station_dict_edit = station_dict.copy()

# station_dictに登録されているが詳細がまったくないデータを追加
# incompleteの方
for station in station_dict_edit:
    # データがあるものは無視
    if 'geo:lat' in station:
        continue

    # データを拾ってくる
    new_data = incomplete_stations_annotated[
        (incomplete_stations_annotated['dc:title'] == station['dc:title']) &
        (incomplete_stations_annotated['odpt:railway'] == station['odpt:railway']) &
        (incomplete_stations_annotated['odpt:operator'] == station['odpt:operator'])
    ]

    if not new_data.empty:
        new_data = new_data.iloc[0]

        for c in ['geo:lat', 'geo:long']:
            station[c] = new_data[c]

        # 乗り換え駅については、元データが存在せず、かつ新データがnanでない場合に登録
        for c in ['odpt:connectingRailway', 'odpt:connectingStation']:
            # nanの判定はfloatであることを挟まないとエラーが出る
            if c not in station and not (isinstance(new_data[c], (float, type(None))) and pd.isna(new_data[c])):
                station[c] = new_data[c]   

# 抜けている駅を追加する
for idx, row in missing_df_annotated.iterrows():
    new_station = {}

    # 追加する列
    columns = ['dc:title', 'odpt:railway', 'odpt:operator', 'geo:lat', 'geo:long', 'owl:sameAs', 'odpt:stationCode', 'odpt:stationTitle', 'odpt:stationTimetable', 'odpt:connectingRailway', 'odpt:connectingStation']

    for c in columns:
        if not (isinstance(row[c], (float, type(None))) and pd.isna(row[c])):
            new_station[c] = row[c]
    
    station_dict_edit.append(new_station)

# StationOrderを並び替え

# 対象の事業者
operator_ids = [n['owl:sameAs'] for n in operator_dict_edit if n['dc:title'] in additional_operators]

railway_dict_ordered = copy.deepcopy(railway_dict_edit)

# 東京駅の座標：上下線の判定で使用
tokyo_st = gpd.GeoSeries(shapely.Point(139.7671, 35.6812), crs = 'EPSG:4326').to_crs(crs)[0]

# 順番を手動指定する路線
manual_orders = {
    'ディズニーリゾートライン': ['リゾートゲートウェイ・ステーション', '東京ディズニーランド･ステーション', 'ベイサイド･ステーション', '東京ディズニーシー･ステーション', 'リゾートゲートウェイ・ステーション'],
    'ユーカリが丘線': ['ユーカリが丘', '地区センター', '公園', '女子大', '中学校', '井野', '公園', '地区センター', 'ユーカリが丘'],
    '箱根登山線': ['小田原', '箱根板橋', '風祭', '入生田', '箱根湯本', '塔ノ沢', '大平台', '宮ノ下', '小涌谷', '彫刻の森', '強羅']
}

for n in railway_dict_ordered:
    # データが無いものについてデータを作成
    if (n['odpt:stationOrder'] == []) and (n['odpt:operator'] in operator_ids):
        r = n['owl:sameAs']
        print(n['dc:title'])
        geometry = rail_merge_temp[rail_merge_temp['odpt:railway'] == r].iloc[0]['geometry']
        print(geometry)

        # 該当路線上の駅を抽出
        rail_stations = [s for s in station_dict_edit if s['odpt:railway'] == r]
        df_temp = pd.DataFrame.from_dict(rail_stations)
        gdf_temp = gpd.GeoDataFrame(df_temp, geometry = gpd.points_from_xy(df_temp['geo:long'], df_temp['geo:lat']), crs = 'EPSG:4326').to_crs(crs)
        # 始点からの距離で並べ替え
        # 始点は国土数値情報上のあれなので不明
        gdf_temp['distance'] = gdf_temp['geometry'].apply(lambda point: shapely.line_locate_point(geometry, point))
        gdf_temp.sort_values(by = 'distance', inplace = True, ignore_index = True)

        # 上下線の判定：両端の東京駅からの距離を比較し、東京駅に近い方を起点（下りの出発点）とする。
        # もし現状で逆となっていたら順番を入れ替える
        head_dist = shapely.distance(tokyo_st, gdf_temp.iloc[0]['geometry'])
        tail_dist = shapely.distance(tokyo_st, gdf_temp.iloc[-1]['geometry'])
        if head_dist > tail_dist:
            gdf_temp = gdf_temp.iloc[::-1].reset_index()

        # 起終点が逆になってしまう路線は手動で変更
        reversed_lines = ['江ノ島電鉄線', '上毛線', '大雄山線']
        if n['dc:title'] in reversed_lines:
            gdf_temp = gdf_temp.iloc[::-1].reset_index()          

        # stationOrderのデータを作成
        station_order = []

        # 個別対応する路線        
        if n['dc:title'] in manual_orders:
            for idx, st in enumerate(manual_orders[n['dc:title']]):
                row = gdf_temp[gdf_temp['odpt:stationTitle'].apply(lambda x: x['ja'] == st)].iloc[0]
                station_order.append({
                    'odpt:index': idx + 1,
                    'odpt:station': row['owl:sameAs'],
                    'odpt:stationTitle': row['odpt:stationTitle']                   
                })

        # それ以外
        else:
            station_order = [{
                'odpt:index': idx + 1,
                'odpt:station': row['owl:sameAs'],
                'odpt:stationTitle': row['odpt:stationTitle']
            } for idx, row in gdf_temp.iterrows()]

        n['odpt:stationOrder'] = station_order

edit_fp = os.path.join('..', 'data', 'ksj', 'edit')
os.makedirs(edit_fp, exist_ok = True)

# データの保存
with open(os.path.join(edit_fp, 'operators_edit.json'), 'w') as f:
    json.dump(operator_dict_edit, f)
with open(os.path.join(edit_fp, 'railways_edit.json'), 'w') as f:
    json.dump(railway_dict_ordered, f)
with open(os.path.join(edit_fp, 'stations_edit.json'), 'w') as f:
    json.dump(station_dict_edit, f)

edit_fp = os.path.join('..', 'data', 'ksj', 'edit')
os.makedirs(edit_fp, exist_ok = True)

with open(os.path.join(edit_fp, 'operators_edit.json'), 'r') as f:
    operator_dict_edit = json.load(f)
with open(os.path.join(edit_fp, 'railways_edit.json'), 'r') as f:
    railway_dict_ordered = json.load(f)
with open(os.path.join(edit_fp, 'stations_edit.json'), 'r') as f:
    station_dict_edit = json.load(f)

# 追加の事業者ID一覧
additional_operators_id = [n['owl:sameAs'] for n in operator_dict_edit if n['odpt:operatorTitle']['ja'] in additional_operators]

path_missing = os.path.join('..', 'data', 'odpt_api', 'missing_generated')
os.makedirs(path_missing, exist_ok = True)

for rail in railway_dict_ordered:
    # 新たな事業者以外はスキップ
    if rail['odpt:operator'] not in additional_operators_id:
        continue

    # 情報を保存
    line_id = rail['owl:sameAs']
    line_name = rail['dc:title']
    st_name_list = [n['odpt:stationTitle']['ja'] for n in rail['odpt:stationOrder']]
    st_id_list = [n['odpt:station'] for n in rail['odpt:stationOrder']]

    df_outbound = pd.DataFrame({
        'source_id': st_id_list[:-1],
        'target_id': st_id_list[1:],
        'source_name': st_name_list[:-1],
        'target_name': st_name_list[1:]
    })

    df_inbound = pd.DataFrame({
        'source_id': reversed(st_id_list[1:]),
        'target_id': reversed(st_id_list[:-1]),
        'source_name': reversed(st_name_list[1:]),
        'target_name': reversed(st_name_list[:-1])        
    })

    for df in [df_outbound, df_inbound]:
        df['line_id'] = line_id
        df['type_id'] = ''
        df['line_name'] = line_name
        df['type_name'] = ''
    
    df_outbound['direction'] = 'odpt.RailDirection:Outbound'
    df_inbound['direction'] = 'odpt.RailDirection:Inbound'
    
    # 入力用の欄
    for df in [df_outbound, df_inbound]:
        df['duration'] = 0
        df['waiting_time'] = 0

    fn_outbound = f"{line_id.split(':')[-1]}_Outbound.csv"
    df_outbound.to_csv(os.path.join(path_missing, fn_outbound), encoding='cp932', index = False)    
    fn_inbound = f"{line_id.split(':')[-1]}_Inbound.csv"
    df_inbound.to_csv(os.path.join(path_missing, fn_inbound), encoding='cp932', index = False)    

# 路線情報を漁る用のファイル作成
railway_data_dict = []

for railway in railway_dict_ordered:
    operator_id = railway['odpt:operator']
    railway_id = railway['owl:sameAs']
    railway_name = railway['odpt:railwayTitle']
    operator_name = [n for n in operator_dict_edit if n['owl:sameAs'] == operator_id][0]['odpt:operatorTitle']

    data_temp = {
        'operator_id': operator_id,
        'operator_name': operator_name,
        'railway_id': railway_id,
        'railway_name': railway_name
    }

    railway_data_dict.append(data_temp)

edit_fp = os.path.join('..', 'data', 'ksj', 'edit')
os.makedirs(edit_fp, exist_ok = True)

with open(os.path.join(edit_fp, 'railway_data.json'), 'w') as f:
    json.dump(railway_data_dict, f)



