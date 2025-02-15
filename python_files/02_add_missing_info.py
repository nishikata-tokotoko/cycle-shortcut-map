# ない路線の情報を補完
# 列車時刻表がない路線：列車時刻表を補完
# そもそもデータがない路線：国土数値情報からデータを生成

import pandas as pd
import geopandas as gpd
import os
import json
import pickle
import re
from datetime import datetime

# 列車時刻表だけがない路線

# 元のパス
path_odpt = os.path.join('..', 'data', 'odpt_api', 'challenge')

# 保存するパス
# 現在は同じだが必要に応じて変更
path_edit = os.path.join('data', 'odpt_api', 'challenge')

# 保存先のフォルダが存在しない場合は作成
os.makedirs(path_edit, exist_ok = True)

# 駅データを読み込み
with open(os.path.join(path_odpt, 'Station.json'), 'r') as f:
    station_dict = json.load(f)

# 事業者データを読み込み
with open(os.path.join(path_odpt, 'Operator.json'), 'r') as f:
    operator_dict = json.load(f)

# 路線データを読み込み
with open(os.path.join(path_odpt, 'Railway.json'), 'r') as f:
    railway_dict = json.load(f)

# 駅時刻表を読み込み
with open(os.path.join(path_odpt, 'StationTimetable.json'), 'r') as f:
    s_timetable_dict = json.load(f)

# 路線時刻表を読み込み
with open(os.path.join(path_odpt, 'TrainTimetable.json'), 'r') as f:
    t_timetable_dict = json.load(f)

# 種別情報を読み込み
with open(os.path.join(path_odpt, 'TrainType.json'), 'r') as f:
    train_type = json.load(f)

# 時刻表データ
start_time = 11
end_time = 15

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

# 路線時刻表が無いすべての路線 - いろいろ含まれてしまう
no_data_lines = [r['owl:sameAs'] for r in railway_dict if r['owl:sameAs'] not in duration_list.keys()]

# 駅時刻表はあるけど路線時刻表にない路線
missing_lines = [line for line in set([n for key, value in waiting_time_dict.items() for n in value.keys()]) if line not in duration_list.keys()]

# 各路線の種別データを作成
railway_type_data = {}

for _, data_dict in waiting_time_dict.items():
    for line, line_data in data_dict.items():
        # データが有るのは無視
        if line not in no_data_lines:
            continue

        if line not in railway_type_data:
            railway_type_data[line] = {}
        
        for direction, types in line_data.items():
            if direction not in railway_type_data[line]:
                railway_type_data[line][direction] = []
            for t in types:
                if t not in railway_type_data[line][direction]:
                    railway_type_data[line][direction].append(t)

# 各路線の駅リストを作成
station_lists = {}

for r in railway_dict:
    rail_id = r['owl:sameAs']
    if rail_id not in missing_lines:
        continue
    station_lists[rail_id] = {
        'id': [s['odpt:station'] for s in r['odpt:stationOrder']],
        'name': [s['odpt:stationTitle']['ja'] for s in r['odpt:stationOrder']]
    }

# 各路線・種別ごとの入力用ファイルを作成
path_missing = os.path.join('..', 'data', 'odpt_api', 'missing')
os.makedirs(path_missing, exist_ok = True)

for line, line_data in railway_type_data.items():
    station_lists[line]
    for direction, train_types in line_data.items():
        df_temp = pd.DataFrame()
        if direction == 'odpt.RailDirection:Outbound':
            df_temp = pd.DataFrame({
                'source_id': station_lists[line]['id'][:-1],
                'target_id': station_lists[line]['id'][1:],
                'source_name': station_lists[line]['name'][:-1],
                'target_name': station_lists[line]['name'][1:]
            })
        else:
            df_temp = pd.DataFrame({
                'source_id': reversed(station_lists[line]['id'][1:]),
                'target_id': reversed(station_lists[line]['id'][:-1]),
                'source_name': reversed(station_lists[line]['name'][1:]),
                'target_name': reversed(station_lists[line]['name'][:-1])
            })

        for t in train_types:
            df_temp['line_id'] = line
            df_temp['type_id'] = t
            line_name = [d['dc:title'] for d in railway_dict if d['owl:sameAs'] == line][0]
            type_name = [d['dc:title'] for d in train_type if d['owl:sameAs'] == t][0]

            df_temp['line_name'] = line_name
            df_temp['type_name'] = type_name
            
            df_temp['direction'] = direction    
            df_temp['duration'] = 0

            fn = f"{line.split(':')[-1]}_{direction.split(':')[-1]}_{t.split(':')[-1]}.csv"
            df_temp.to_csv(os.path.join(path_missing, fn), encoding = 'cp932', index = False)

path_edited = os.path.join('..', 'data', 'odpt_api', 'missing_edited')

# CSVファイルの一覧
csv_files = [entry for entry in os.listdir(path_edited) 
             if os.path.isfile(os.path.join(path_edited, entry)) and entry.endswith('.csv')]

# 所要時間を保存するリスト
added_duration_dict = {}

for fn in csv_files:
    try:
        df_temp = pd.read_csv(os.path.join(path_edited, fn))
    except UnicodeDecodeError:
        df_temp = pd.read_csv(os.path.join(path_edited, fn), encoding='cp932')

    for _, row in df_temp.iterrows():
        line_id = row['line_id']
        direction_id = row['direction']
        type_id = row['type_id']

        if line_id not in added_duration_dict:
            added_duration_dict[line_id] = {}
        
        if type_id not in added_duration_dict[line_id]:
            added_duration_dict[line_id][type_id] = {}
        
        if direction_id not in added_duration_dict[line_id][type_id]:
            added_duration_dict[line_id][type_id][direction_id] = {}
        
        added_duration_dict[line_id][type_id][direction_id][(row['source_id'], row['target_id'])] = {
            'duration_mins': float(row['duration'])
        }

# ----- データが全く存在しないもの -----
path_gen_edited = os.path.join('..', 'data', 'odpt_api', 'missing_generated_edited')

# Get a list of all .csv files
csv_files = [entry for entry in os.listdir(path_gen_edited) if os.path.isfile(os.path.join(path_gen_edited, entry)) and entry.endswith('.csv')]

for fn in csv_files:
    try:
        df_temp = pd.read_csv(os.path.join(path_gen_edited, fn))
    except UnicodeDecodeError:
        df_temp = pd.read_csv(os.path.join(path_gen_edited, fn), encoding='cp932')

    for _, row in df_temp.iterrows():
        line_id = row['line_id']
        direction_id = row['direction']
        type_id = row['type_id']

        if line_id not in added_duration_dict:
            added_duration_dict[line_id] = {}
        
        if type_id not in added_duration_dict[line_id]:
            added_duration_dict[line_id][type_id] = {}
        
        if direction_id not in added_duration_dict[line_id][type_id]:
            added_duration_dict[line_id][type_id][direction_id] = {}
        
        added_duration_dict[line_id][type_id][direction_id][(row['source_id'], row['target_id'])] = {
            'duration_mins': float(row['duration'])
        }

# 列車種別

# 元のパス
path_odpt = os.path.join('..', 'data', 'odpt_api', 'challenge')

# 種別情報を読み込み
with open(os.path.join(path_odpt, 'TrainType.json'), 'r') as f:
    train_type = json.load(f)

path_gen_edited = os.path.join('..', 'data', 'odpt_api', 'missing_generated_edited')

# Get a list of all .csv files
csv_files = [entry for entry in os.listdir(path_gen_edited) if os.path.isfile(os.path.join(path_gen_edited, entry)) and entry.endswith('.csv')]

# 平均待ち時間のdict
waiting_time_dict = {}

for fn in csv_files:
    try:
        df_temp = pd.read_csv(os.path.join(path_gen_edited, fn))
    except UnicodeDecodeError:
        df_temp = pd.read_csv(os.path.join(path_gen_edited, fn), encoding='cp932')

    for _, row in df_temp.iterrows():
        # 各種情報の取得
        line_id = row['line_id']
        direction_id = row['direction']
        type_id = row['type_id']
        type_name = row['type_name']
        station_id = row['source_id']
        waiting_time = row['waiting_time']


        
        # 事業者IDを路線IDから生成
        operator_id = f"odpt.Operator:{line_id.split(':')[1].split('.')[0]}"

        # 種別関連処理
        if type_id not in [n['owl:sameAs'] for n in train_type]:
            # print(type_id)
            # 種別の英語名をIDのcamelCaseからTitle Caseにすることで錬成
            type_name_en = re.sub(r'(?<!^)(?=[A-Z])', ' ', type_id.split('.')[-1]).title().replace('- ', '-')

            type_data = {
                '@type': 'odpt:TrainType',
                'dc:title': type_name,
                'owl:sameAs': type_id,
                'odpt:operator': operator_id,
                'odpt:trainTypeTitle': {
                    'en': type_name_en,
                    'ja': type_name
                }
            }
            train_type.append(type_data)

        # 待ち時間関連処理
        if station_id not in waiting_time_dict:
            waiting_time_dict[station_id] = {}
        if line_id not in waiting_time_dict[station_id]:
            waiting_time_dict[station_id][line_id] = {}
        if direction_id not in waiting_time_dict[station_id][line_id]:
            waiting_time_dict[station_id][line_id][direction_id] = {}
        
        waiting_time_dict[station_id][line_id][direction_id][type_id] = waiting_time

# 所要時間を保存
with open(os.path.join(path_edited, 'duration_dict.pkl'), 'wb') as f:
    pickle.dump(added_duration_dict, f)

# 種別データを保存
edit_fp = os.path.join('..', 'data', 'ksj', 'edit')
os.makedirs(edit_fp, exist_ok = True)

with open(os.path.join(edit_fp, 'train_type_edit.json'), 'w') as f:
    json.dump(train_type, f)

# 平均待ち時間を保存
with open(os.path.join(path_gen_edited, 'waiting_time_dict.pkl'), 'wb') as f:
    pickle.dump(waiting_time_dict, f)


# 文字コードの修正
path_orig = [os.path.join('..', 'data', 'odpt_api', 'missing_edited_orig'), os.path.join('..', 'data', 'odpt_api', 'missing_generated_edited_orig')]
path_fixed = [os.path.join('..', 'data', 'odpt_api', 'missing_edited'), os.path.join('..', 'data', 'odpt_api', 'missing_generated_edited')]

for i in [0, 1]:
    # 新しいフォルダを作る
    os.makedirs(path_fixed[i], exist_ok = True)

    csv_files = [entry for entry in os.listdir(path_orig[i]) if os.path.isfile(os.path.join(path_orig[i], entry)) and entry.endswith('.csv')]

    for fn in csv_files:
        try:
            df_temp = pd.read_csv(os.path.join(path_orig[i], fn))
        except UnicodeDecodeError:
            df_temp = pd.read_csv(os.path.join(path_orig[i], fn), encoding='cp932')

        df_temp.to_csv(os.path.join(path_fixed[i], fn), encoding='cp932')

