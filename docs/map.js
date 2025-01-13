import { buildGraphLookup, dijkstra, dijkstra_multiple, parsePath, displayPath } from "./search.js";
// import { fetchGBFS, updateFromAPI, updateAvailability, buildH3Index } from "./cycleData.js"

// ----- グローバル変数 -----

let startingStationName = document.getElementById('sourceStation').value;
let selectedStationName = '';
let clickedStationName = '';
let cycleMinDist = Number(document.getElementById('cycleMinDist').value);
let cycleMaxDist = Number(document.getElementById('cycleMaxDist').value);
let extraTimeAllowed = Number(document.getElementById('extraTime').value);
let sharedCycleOnly = document.getElementById('sharedCycleOnly');
let serviceSelected = document.getElementById('cyclingServiceRadioForm')['cyclingServiceRadio'].value;
let maxDistInput = Number(document.getElementById('portKRings').value);
let showCycleLayerFlag = false;
let cycleStationName = '';

// ----- UI関連 -----

// シェアサイクルのところのUI
document.getElementById('sharedCycleOnly').addEventListener('change', function() {
    const form = document.getElementById('shareCycleOptions');
    if (this.checked) {
        form.classList.add('show');
    } else {
        form.classList.remove('show');
    }

});

// 距離スライダーの更新
function updateDistSlider () {
    maxDistInput = Number(document.getElementById('portKRings').value);
    const maxDist = (maxDistInput + 1) * 50;
    document.getElementById('portKRingsShow').textContent = `約 ${maxDist} [m]`;
}

// ----- 地図関連 -----

// 初期化
const map = new maplibregl.Map({
    container: 'map',
    style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
    center: [139.75, 35.69],
    zoom: 11,
    minZoom: 7,
});


// スケールバー
let scale = new maplibregl.ScaleControl({
    maxWidth: 80,
    unit: 'metric',
});
map.addControl(scale);

// ----- 自転車関連 -----

// GBFSのデータの取得
function fetchGBFS (source, id) {
    const data = source.data.stations.filter((station) => station.station_id === id)[0];
    return data;
}

// データを更新
// Promiseを返すように設定
function updateFromAPI (source_id, url) {
    return fetch(url)
        .then((response) => response.json())
        .then((statusData) => {
            updateAvailability(source_id, statusData);
        });
}

function updateAvailability (source_id, status) {
    const source = map.getSource(source_id);
    const features = source._data.features;

    features.forEach(feature => {
        const station_id = feature.properties.station_id;
        const data = fetchGBFS(status, station_id);
        if (data) {
            feature.properties.availability = data.num_bikes_available;
            feature.properties.dock_availability = data.num_docks_available;
            feature.properties.calc_capacity = Number(data.num_bikes_available) + Number(data.num_docks_available);
        } else {
            feature.properties.availability = 0;
        };
    });
    source.setData(source._data);
}

// H3のIndexを構築
function buildH3Index(features) {
    const index = new Map();
    features.forEach((feature) => {
        const h3Index = feature.properties.h3_index;
        if (!index.has(h3Index)) {
            index.set(h3Index, []);
        }
        index.get(h3Index).push(feature);
    });
    return index;
}

// main map
map.on('load', function(){
    Promise.all([
        fetch('doc_data/railway_data.json').then((response) => response.json()),
        fetch('doc_data/ksj_railways.geojson').then((response) => response.json()),
        fetch('doc_data/tokyo_stations_bet.geojson').then((response) => response.json()),
        fetch('doc_data/train_type_edit.json').then((response) => response.json()),
        fetch('doc_data/tokyo_graph_layered.json').then((response) => response.json()),
        fetch('doc_data/hello_ports.geojson').then((response) => response.json()),        
        fetch('doc_data/docomo_ports.geojson').then((response) => response.json()),
    ]).then(([railData, railGeom, stationGeom, trainType, graphData, helloPorts, docomoPorts]) => {
        // 不要なものを削除
        stationGeom.features = stationGeom.features.filter((feature) => !(['新前橋', '渋川', '中之条', '長野原草津口'].includes(feature.properties.station_name)));

        // sourceに追加
        map.addSource('railway', {
            type: 'geojson',
            data: railGeom,                
        });
        map.addSource('stationGeom', {
            type: 'geojson',
            data: stationGeom,
            generateId: true
        });           
        map.addSource('h_docks', {
            type: 'geojson',
            data: helloPorts,
            generateId: true
        });
        map.addSource('d_docks', {
            type: 'geojson',
            data: docomoPorts,
            generateId: true
        });

        // 空のソース
        map.addSource('path', {
            type: 'geojson',
            data: {
                'type': 'FeatureCollection',
                'features': []
            }
        });

        
        // ----- 変数の定義 -----

        // 駅情報表示のためのポップアップ
        const stationPopup = new maplibregl.Popup({
            closeButton: false,
            closeOnClick: false,
            anchor: 'bottom-left',
            offset: 5
        });

        // 駐輪場情報表示のためのポップアップ
        const cyclePopup = new maplibregl.Popup({
            closeButton: false,
            closeOnClick: false,
            anchor: 'top-left',
            offset: 5
        });

        // create list of stations
        const stationList = [];
        stationGeom.features.forEach((feature) => {
            if (feature.properties.station_name) {
                stationList.push(feature.properties.station_name);
            }
        });
        // 自動入力
        stationList.forEach((station) => {
            let option = document.createElement('option');
            option.value = station;
            document.getElementById('stationList').appendChild(option);
        });

        // H3 Index
                
        // Precompute h3 grid disk cache and dock feature indexes
        let gridDiskCache = new Map();
        const dDocksH3Index = buildH3Index(docomoPorts.features);
        const hDocksH3Index = buildH3Index(helloPorts.features);

        // 駅の表示半径
        // ズームレベルで変化
        // 全部一定の場合
        const stationRadiusUniform = [
            'interpolate', ['linear'], ['zoom'],
            8, 4, // size 4 at zoom 8,
            14, 28 // size 28 at zoom 14
        ];

        // 自転車ある無しでサイズ変化する場合
        const stationRadiusVaried = [
            'interpolate', ['linear'], ['zoom'],
            8, [
                'case',
                ['boolean', ['get', 'cycleFlag'], false],
                4,
                1,
            ],
            14, [
                'case',
                ['boolean', ['get', 'cycleFlag'], false],
                28,
                7,
            ]
        ];

        // 経路の線幅
        const pathWidthUniform = [
            'interpolate', ['linear'], ['zoom'],
            8, 2, // size 2 at zoom 8,
            14, 14 // size 14 at zoom 14
        ];
        // 10太いやつ
        const pathWidthUniformWide = [
            'interpolate', ['linear'], ['zoom'],
            8, 12,
            14, 29
        ];

        // 出発駅レイヤーを追加
        map.addLayer({
            'id': 'startingStation',
            'type': 'circle',
            'source': 'stationGeom',
            'layout': {
                'circle-sort-key': 6,
            },
            'paint': {
                'circle-radius': stationRadiusUniform,
                'circle-color': '#004080',
                'circle-stroke-width': 4,
                'circle-stroke-color': '#ffffff'
            }
        });
        map.setFilter('startingStation', false);
        
        // 到着駅レイヤーを追加
        map.addLayer({
            'id': 'clickedStation',
            'type': 'circle',
            'source': 'stationGeom',
            'layout': {
                'circle-sort-key': 6,
            },
            'paint': {
                'circle-radius': stationRadiusUniform,
                'circle-color': '#004080',
                'circle-stroke-width': 4,
                'circle-stroke-color': '#ffffff',
                'circle-stroke-opacity': 1
                // 'circle-opacity': 0,
                // 'circle-stroke-color': '#004080',
            }
        });
        map.setFilter('clickedStation', false);

        // 出発駅ラベル
        map.addLayer({
            'id': 'startingStationLabel',
            'type': 'symbol',
            'source': 'stationGeom',
            'layout': {
                'text-field': 'S',
                'text-size': [
                    'interpolate', ['linear'], ['zoom'],
                    9.995, 0,
                    10, 12,
                    14, 28,
                ],
                'text-font': [
                    'Open Sans Bold',
                    'Arial Unicode MS Bold',
                ],  
            },
            'paint': {
                'text-color': '#ffffff',
                'text-opacity': 1
            }
        });
        map.setFilter('startingStationLabel', false);

        // 到着駅ラベル
        map.addLayer({
            'id': 'clickedStationLabel',
            'type': 'symbol',
            'source': 'stationGeom',
            'layout': {
                'text-field': 'G',
                'text-size': [
                    'interpolate', ['linear'], ['zoom'],
                    9.995, 0,
                    10, 12,
                    14, 28,
                ],
                'text-font': [
                    'Open Sans Bold',
                    'Arial Unicode MS Bold',
                ],  
            },
            'paint': {
                'text-color': '#ffffff',
                'text-opacity': 1
            }
        });
        map.setFilter('clickedStationLabel', false);
        // 経路レイヤー
        map.addLayer({
            id: 'path',
            type: 'line',
            source: 'path',
            paint: {
                'line-color': [
                    'case',
                    ['==', ['get', 'pathType'], 'forceCycle'],                 '#004080',
                    ['==', ['get', 'pathType'], 'noCycle'], '#6699CC',
                    '#ffffff'
                ],
                'line-width': pathWidthUniform,
            },
            layout: {
                'line-cap': 'round',
                'line-join': 'round'
            }
        }, 'startingStation');

        // 選んだ経路レイヤー
        map.addLayer({
            id: 'pathChosen',
            type: 'line',
            source: 'path',
            paint: {
                'line-color': '#DAA520',
                'line-width': pathWidthUniformWide,
                'line-blur': 5,
            },
            layout: {
                'line-cap': 'round',
                'line-join': 'round'
            }
        }, 'path');
        map.setFilter('pathChosen', false);
        

        // ----- 自転車関連関数 -----

        // 自転車のアップデート
        updateCycleStatus();
        // 最大距離の更新
        document.getElementById('portKRings').addEventListener('input', () => {
            // リセット
            gridDiskCache = new Map();
            updateDistSlider();
            updateAggCycleStatus();
            updateCyclingGraphLookup();
            updateView();

        });
        document.getElementById('sharedCycleOnly').addEventListener('input', () => {
            serviceSelected = document.getElementById('cyclingServiceRadioForm')['cyclingServiceRadio'].value;
            updateAggCycleStatus();
            updateCyclingGraphLookup();
            updateView();
        });
        document.getElementById('cyclingServiceRadioForm').addEventListener('input', () => {
            serviceSelected = document.getElementById('cyclingServiceRadioForm')['cyclingServiceRadio'].value;
            updateAggCycleStatus();
            updateCyclingGraphLookup();
            updateView();
        });

        // APIから空き状況を拾ってくる
        function updateCycleStatus() {
            // update time display
            const timestamp = new Date();
            // const formatTime = timestamp.toLocaleString();
            // document.getElementById("timestamp").innerHTML = "Availability last updated: " + formatTime;

            Promise.all([
                updateFromAPI('d_docks', 'https://api-public.odpt.org/api/v4/gbfs/docomo-cycle/station_status.json'),
                updateFromAPI('h_docks', 'https://api-public.odpt.org/api/v4/gbfs/hellocycling/station_status.json')          
            ]).then(() => {
                updateAggCycleStatus();

            });
        }

        // 駅単位で集計範囲を変更して再集計
        function updateAggCycleStatus() {
            maxDistInput = Number(document.getElementById('portKRings').value);
            const stationSource = map.getSource('stationGeom');
            const features = stationSource._data.features;


            features.forEach((feature) => {
                const h3Index = feature.properties.h3_index;
        
                // Use cached gridDisk if available
                if (!gridDiskCache.has(h3Index)) {
                    gridDiskCache.set(h3Index, h3.gridDisk(h3Index, maxDistInput));
                }
                const gridDisk = gridDiskCache.get(h3Index);
        
                const aggAvail = aggCycleStatus(gridDisk, hDocksH3Index, dDocksH3Index);
        
                // Update feature properties
                Object.assign(feature.properties, {
                    helloAvailableCycles: aggAvail.hello.availability,
                    helloAvailableDocks: aggAvail.hello.dockAvailability,
                    helloCapacity: aggAvail.hello.calcCapacity,
                    helloNumPorts: aggAvail.hello.numPorts,
                    docomoAvailableCycles: aggAvail.docomo.availability,
                    docomoAvailableDocks: aggAvail.docomo.dockAvailability,
                    docomoCapacity: aggAvail.docomo.calcCapacity,
                    docomoNumPorts: aggAvail.docomo.numPorts,
                    totalAvailableCycles: aggAvail.total.availability,
                    totalAvailableDocks: aggAvail.total.dockAvailability,
                    totalCapacity: aggAvail.total.calcCapacity,
                    totalNumPorts: aggAvail.total.numPorts,
                });
            });
        
            stationSource.setData(stationSource._data);
            // console.log('Updated Cycle Status');

        }
        // H3のグリッドk個分にある空き自転車の数を集計
        function aggCycleStatus(gridDisk, hDocksIndex, dDocksIndex) {
            let aggAvail = {
                hello: { availability: 0, dockAvailability: 0, calcCapacity: 0, numPorts: 0 },
                docomo: { availability: 0, dockAvailability: 0, calcCapacity: 0, numPorts: 0 },
                total: { availability: 0, dockAvailability: 0, calcCapacity: 0, numPorts: 0 },
            };
        
            gridDisk.forEach((h3Index) => {
                if (hDocksIndex.has(h3Index)) {
                    hDocksIndex.get(h3Index).forEach((feature) => {
                        aggAvail.hello.availability += feature.properties.availability ?? 0;
                        aggAvail.hello.dockAvailability += feature.properties.dock_availability ?? 0;
                        aggAvail.hello.calcCapacity += feature.properties.calc_capacity ?? 0;
                        aggAvail.hello.numPorts++;
                    });
                }
                if (dDocksIndex.has(h3Index)) {
                    dDocksIndex.get(h3Index).forEach((feature) => {
                        aggAvail.docomo.availability += feature.properties.availability ?? 0;
                        aggAvail.docomo.dockAvailability += feature.properties.dock_availability ?? 0;
                        aggAvail.docomo.calcCapacity += feature.properties.calc_capacity ?? 0;
                        aggAvail.docomo.numPorts++;
                    });
                }
            });
        
            aggAvail.total.availability = aggAvail.hello.availability + aggAvail.docomo.availability;
            aggAvail.total.dockAvailability = aggAvail.hello.dockAvailability + aggAvail.docomo.dockAvailability;
            aggAvail.total.calcCapacity = aggAvail.hello.calcCapacity + aggAvail.docomo.calcCapacity;
            aggAvail.total.numPorts = aggAvail.hello.numPorts + aggAvail.docomo.numPorts;
        
            return aggAvail;
        }

        // 自転車レイヤーを追加するが全部非表示に
        map.addLayer({
            'id': 'h_docks',
            'type': 'circle',
            'source': 'h_docks',
            'layout': {
                'circle-sort-key': 7,
            },
            'paint': {
                'circle-radius': [
                    'interpolate', ['linear'], ['zoom'],
                    8, 3,
                    14, 21
                ],
                'circle-color': '#ffdd00',
                'circle-stroke-width': 3,
                'circle-stroke-color': '#ffffff'
            }
        });
        map.setFilter('h_docks', false);

        map.addLayer({
            'id': 'd_docks',
            'type': 'circle',
            'source': 'd_docks',
            'layout': {
                'circle-sort-key': 7,
            },
            'paint': {
                'circle-radius': [
                    'interpolate', ['linear'], ['zoom'],
                    8, 3,
                    14, 21
                ],
                'circle-color': '#dd0000',
                'circle-stroke-width': 3,
                'circle-stroke-color': '#ffffff',
            }
        });
        map.setFilter('d_docks', false);

        // ----- グラフ関連関数 -----

        // graphData for calculations
        let graphDataCalc = structuredClone(graphData);
        let graphLookup;
        function updateCyclingGraphLookup() {
            cycleMinDist = Number(document.getElementById('cycleMinDist').value);
            cycleMaxDist = Number(document.getElementById('cycleMaxDist').value);
            document.getElementById('cycleMinDistShow').textContent = `${cycleMinDist} [km]`;
            document.getElementById('cycleMaxDistShow').textContent = `${cycleMaxDist} [km]`;

            // 距離が長過ぎる・短すぎるチャリエッジは削除
            graphDataCalc.links = graphData.links.filter((link) => !(link.link_type === 'cycle' && (link.distance > (cycleMaxDist * 1000) || link.distance < cycleMinDist * 1000)));

            // シェアサイクルのみ使用する場合、ポートがない駅についてはノード（とエッジ）を消去
            if (sharedCycleOnly.checked) {
                let noCycleStations = [];
                switch (serviceSelected) {
                    case 'hello':
                        stationGeom.features.forEach((feature) => {
                            if (Number(feature.properties.helloNumPorts) === 0) {
                                noCycleStations.push(feature.properties.station_name);
                            }
                        });
                        break;
                    case 'docomo':
                        stationGeom.features.forEach((feature) => {
                            if (Number(feature.properties.docomoNumPorts) === 0) {
                                noCycleStations.push(feature.properties.station_name);
                            }
                        });                        
                        break;
                    case 'total':
                        stationGeom.features.forEach((feature) => {
                            if (Number(feature.properties.totalNumPorts) === 0) {
                                noCycleStations.push(feature.properties.station_name);
                            }
                        }); 
                        break;
                    
                }

                let removeNodes = [];
                noCycleStations.forEach((station) => {
                    removeNodes.push(`${station}_cycle_on`);
                    removeNodes.push(`${station}_cycle_off`);
                    removeNodes.push(`AC+${station}_cycle_on`)
                    removeNodes.push(`AC+${station}_cycle_off`);
                });

                const removeNodesSet = new Set(removeNodes);
                // console.log(removeNodesSet);
                graphDataCalc.nodes = graphData.nodes.filter((node) => !removeNodesSet.has(node.id));

                graphDataCalc.links = graphDataCalc.links.filter((link) => !(removeNodesSet.has(link.source) || removeNodesSet.has(link.target)));
            } else {
                // シェアサイクル以外も使う場合は全部のノードを入れる
                graphDataCalc.nodes = graphData.nodes.slice();
            }
            graphLookup = buildGraphLookup(graphDataCalc);

        }

        updateCyclingGraphLookup();

        // graphData for no cycles
        // remove all cycle links
        // remove second layer
        let graphDataNoCycle = structuredClone(graphData);
        graphDataNoCycle.links = graphData.links.filter((link) => (link.link_type !== 'cycle' && !(link.target.includes('AC+'))));
        graphDataNoCycle.nodes = graphData.nodes.filter((node) => !(node.id.includes('AC+')));
        let graphLookupNoCycle = buildGraphLookup(graphDataNoCycle);


        // 出発駅の変更
        function updateStartingStation () {
            startingStationName = document.getElementById('sourceStation').value;
            clickedStationName = '';
            // filter stations
            map.setFilter(
                'startingStation',
                ['==', ['get', 'station_name'], startingStationName]
            );
            // filter stations
            map.setFilter(
                'startingStationLabel',
                ['==', ['get', 'station_name'], startingStationName]
            );
            map.setFilter('clickedStation', false);            
            map.setFilter('clickedStationLabel', false);

            // 経路ウィンドウを非表示に
            if (document.getElementById('route-contents').style.display === 'block') {
                toggleDiv('route-toggle', 'route-contents', '経路情報を隠す', '経路情報を表示');
            }
            // 経路を非表示
            map.setFilter('path', false);
            map.setFilter('pathChosen', false)

            // move to station
            const newStation = stationGeom.features.filter((feature) => feature.properties.station_name === startingStationName)[0];
            map.flyTo({
                center: newStation.geometry.coordinates,
                zoom: 11,
            });

            // 表示をアップデート
            updateView();
        };

        // 画面全体をアップデート
        function updateView () {
            // console.log('Updating View');
            stationPopup.remove();
            // 自転車は消す
            map.setFilter('d_docks', false);
            map.setFilter('h_docks', false);
            const source = map.getSource('stationGeom');
            const features = source._data.features;
            // get input values
            startingStationName = document.getElementById('sourceStation').value;

            // 所要時間のアップデート
            const cycleData = dijkstra_multiple(graphDataCalc, startingStationName + '_source', stationList.map((s) => `AC+` + s + '_target'), graphLookup);
            const noCycleData = dijkstra_multiple(graphDataNoCycle, startingStationName + '_source', stationList.map((s) => s + '_target'), graphLookupNoCycle);

            features.forEach(feature => {
                const stationName = feature.properties.station_name;
                const durationForceCycle = (Number(cycleData.duration[stationName]));
                const durationNoCycle = (Number(noCycleData.duration[stationName]));
                const durationDifference = durationForceCycle - durationNoCycle;
                const shortestDuration = Math.min(durationForceCycle, durationNoCycle);

                // GeoJSONをアップデート
                feature.properties.distForceCycle = durationForceCycle;
                feature.properties.distNoCycle = durationNoCycle;
                feature.properties.distDifference = durationDifference;
                feature.properties.distShortest = shortestDuration;

            });

            source.setData(source._data);
            map.triggerRepaint();
            showCycleLayer();
            updateExtraTime();

        }

        // 許容時間のアップデート
        function updateExtraTime() {
            stationPopup.remove();
            const source = map.getSource('stationGeom');
            const features = source._data.features;

            features.forEach(feature => {
                
                const durationDifference = feature.properties.distDifference;

                // チャリの使用可能性
                const cycleFlag = (durationDifference <= extraTimeAllowed);
                // チャリを許容できればチャリで
                if (cycleFlag) {
                    feature.properties.distCycle = feature.properties.distForceCycle;
                } else {
                    feature.properties.distCycle = feature.properties.distNoCycle;
                }

                feature.properties.cycleFlag = cycleFlag;

            });

            source.setData(source._data);
            updateRoutes();
            
        }

        // 経路表示のアップデート
        function updateRoutes() {
            if (clickedStationName === '') {

                // 到着駅が選択されていない場合表示をリセット
                document.getElementById('routeInfo').innerHTML = '到着駅を地図上で選択してください。'
                document.getElementById('bestTab').innerHTML = '提案経路<hr>';
                document.getElementById('cycleTab').innerHTML = '自転車使用<hr>';
                document.getElementById('noCycleTab').innerHTML = '自転車不使用<hr>';
                document.getElementById('bestRoute').innerHTML = '到着駅を選択してください。'
                document.getElementById('cycleRoute').innerHTML = '到着駅を選択してください。'
                document.getElementById('noCycleRoute').innerHTML = '到着駅を選択してください。'

            } else {
                document.getElementById('routeInfo').innerHTML = `<strong>${startingStationName}</strong>から<strong>${clickedStationName}</strong>まで`;
                // calculate shortest path
                const source = startingStationName + '_source';
                const target = clickedStationName + '_target';
                // 自転車使用可
                const shortestPath = dijkstra(graphDataCalc, source, `AC+` + target, graphLookup);
                const parsedPath = parsePath(graphData, shortestPath.path);
                const resultsData = displayPath(parsedPath, railData, trainType, map.getSource('stationGeom')._data);
                document.getElementById('cycleTab').innerHTML = `自転車使用<br>［${Math.round(resultsData.totalDuration)}分］<hr>`;

                document.getElementById('cycleRoute').innerHTML = `
                    <p>総所要時間： ${Math.round(resultsData.totalDuration)}分</p>
                    ${resultsData.pathTable}
                `;
                // 自転車使用不可
                const shortestPathNoCycle = dijkstra(graphDataNoCycle, source, target, graphLookupNoCycle);
                const parsedPathNoCycle = parsePath(graphData, shortestPathNoCycle.path)
                const resultsDataNoCycle = displayPath(parsedPathNoCycle, railData, trainType, map.getSource('stationGeom')._data);
                document.getElementById('noCycleTab').innerHTML = `自転車不使用<br>［${Math.round(resultsDataNoCycle.totalDuration)}分］<hr>`;
                document.getElementById('noCycleRoute').innerHTML = `
                    <p>総所要時間： ${Math.round(resultsDataNoCycle.totalDuration)}分</p>
                    ${resultsDataNoCycle.pathTable}
                `;
                // 提案経路
                let resultsDataBest;
                if (resultsData.totalDuration <= (resultsDataNoCycle.totalDuration + extraTimeAllowed)) {
                    resultsDataBest = resultsData;
                } else {
                    resultsDataBest = resultsDataNoCycle;
                }
                document.getElementById('bestTab').innerHTML = `提案経路<br>［${Math.round(resultsDataBest.totalDuration)}分］<hr>`;
                document.getElementById('bestRoute').innerHTML = `
                    <p>総所要時間： ${Math.round(resultsDataBest.totalDuration)}分</p>
                    ${resultsDataBest.pathTable}
                `;

                // 経路を追加
                const pathSource = map.getSource('path');
                parsedPath.geometry.forEach((feature) => feature.properties['pathType'] = 'forceCycle');
                parsedPathNoCycle.geometry.forEach((feature) => feature.properties['pathType'] = 'noCycle')
                pathSource._data.features = parsedPathNoCycle.geometry.concat(parsedPath.geometry);
                pathSource.setData(pathSource._data);

                if (resultsData.totalDuration <= (resultsDataNoCycle.totalDuration + extraTimeAllowed)) {
                    map.setFilter(
                        'pathChosen',
                        ['==', ['get', 'pathType'], 'forceCycle']
                    );
                } else {
                    map.setFilter(
                        'pathChosen',
                        ['==', ['get', 'pathType'], 'noCycle']
                    );
                }
                map.setPaintProperty('path', 'line-opacity', 1);
                map.setPaintProperty('pathChosen', 'line-opacity', 1);

            }
            // テーブルにイベントリスナーを追加
            updateTableEventListener();
            showCycleLayer();
        }

        // 経路表示上でのノードをクリックしたときの挙動
        // 当該ノードにズームイン
        // チャリの場合は周辺サイクルポートを表示
        // 3つのテーブルそれぞれに対して、テーブル全体にeventListenerを追加
        function updateTableEventListener() {
            const pathTables = document.querySelectorAll('.pathTable');
            pathTables.forEach((table) => {
                table.addEventListener('click', (event) => {
                    // クリックした行を取得
                    const row = event.target.closest('tr');
                    if (row) {
                        // ノードに対する処理
                        if (row.classList.contains('pathTableNode')) {
                            const rowStationName = row.dataset.stationName;
                            const rowNodeType = row.dataset.nodeType;
                            // console.log(rowStationName);

                            // 駅にズーム
                            const rowStationData = stationGeom.features.filter((feature) => feature.properties.station_name === rowStationName)[0];
                            map.flyTo({
                                center: rowStationData.geometry.coordinates,
                                zoom: 16,
                            });
                            
                            // 自転車レイヤーの表示を更新
                            if (rowNodeType === 'cycle_on' || rowNodeType === 'cycle_off') {
                                showCycleLayerFlag = true;
                            } else {
                                showCycleLayerFlag = false;
                            }

                            cycleStationName = rowStationName;
                            showCycleLayer();
                        }
                    }
                })
            });
        }

        // 自転車レイヤーの表示
        function showCycleLayer() {
            // まずは全消し
            map.setFilter('h_docks', false);
            map.setFilter('d_docks', false);
            // サイクルレイヤーを表示する設定のとき
            if (showCycleLayerFlag) {
                stationGeom
                const newStation = stationGeom.features.filter((feature) => feature.properties.station_name === cycleStationName)[0];
                const h3Index = newStation.properties.h3_index;
                // console.log(h3Index);
                // Use cached gridDisk if available
                if (!gridDiskCache.has(h3Index)) {
                    gridDiskCache.set(h3Index, h3.gridDisk(h3Index, maxDistInput));
                }
                const gridDisk = gridDiskCache.get(h3Index);
                let hDocksList = [];
                let dDocksList = [];
                // add to list
                gridDisk.forEach((h3Index) => {
                    if (hDocksH3Index.has(h3Index)) {
                        hDocksH3Index.get(h3Index).forEach((feature) => {
                            hDocksList.push(feature.properties.station_id);
                        });
                    }
                    if (dDocksH3Index.has(h3Index)) {
                        dDocksH3Index.get(h3Index).forEach((feature) => {
                            dDocksList.push(feature.properties.station_id);
                        });
                    }                      
                });
                // 関係あるものだけ表示
                map.setFilter(
                    'h_docks',
                    ['in', ['get', 'station_id'], ['literal', hDocksList]]
                );
                map.setFilter(
                    'd_docks',
                    ['in', ['get', 'station_id'], ['literal', dDocksList]]
                );                         

            }
        }

        // 地図上に表示する所要時間データの設定
        function setDisplayData() {
            const value = document.getElementById('selectDataRadio')['distSelect'].value;

            let paintField, layoutField;
            let maxValue = 200;
            const magmaPalette = ['#f0f921', '#fca636', '#e16462', '#b12a90', '#6a00a8', '#0d0887'];
            const puRdPalette = ['#f1eef6', '#d4b9da', '#c994c7', '#df65b0', '#dd1c77', '#980043']
            const viridisPalette = ['#fde725', '#7ad151', '#22a884', '#2a788e', '#414487', '#440154'];
            const piYgPalette = ['#d01c8b', '#f1b6da', '#f7f7f7', '#b8e186', '#4dac26'];
            let palette = puRdPalette;

            switch(value) {
                case 'distCycle':
                case 'distCycleOnly':
                    paintField = 'distCycle';
                    layoutField = '{distCycle}';
                    break;
                case 'distNoCycle':
                    paintField = 'distNoCycle';
                    layoutField = '{distNoCycle}';
                    break;
                case 'distForceCycle':
                    paintField = 'distForceCycle';
                    layoutField = '{distForceCycle}';
                    break;
                case 'distCycleOnly':
                    paintField = 'distCycle';
                    layoutField = '{distCycle}';
                    break;
                case 'distDifference':
                    paintField = 'distDifference';
                    layoutField = '{distDifference}';
                    maxValue = 20;
                    palette = piYgPalette;
                    break;
            };
            
            // ラベルの数字を更新
            map.setLayoutProperty('stationGeomLabel', 'text-field', [
                'to-string',
                ['round', ['get', paintField]] // Round the 'distCycle' value
            ]);
            // 小さい数字が上
            map.setLayoutProperty('stationGeom', 'circle-sort-key', [
                '-',
                0,
                ['get', paintField]
            ]);

            if (value === 'distDifference') {
                // 自転車が有効なら色分け
                // 自転車が無効ならグレー
                map.setPaintProperty('stationGeom', 'circle-color', [
                    'case',
                    ['boolean', ['get', 'cycleFlag'], false],
                    [
                        'interpolate',
                        ['linear'],
                        ['get', paintField],
                        -maxValue / 1.5, palette[4],
                        -maxValue / 4, palette[3],
                        0, palette[2],
                        maxValue / 4, palette[1],
                        maxValue / 1.5, palette[0],
                    ],
                    '#cccccc'
                ]);

                // 自転車が無効なら半径を小さく
                map.setPaintProperty('stationGeom', 'circle-radius', stationRadiusVaried);

                // 文字についても自転車が無効なら非表示
                map.setPaintProperty('stationGeomLabel', 'text-opacity', [
                    'case',
                    ['boolean', ['get', 'cycleFlag'], false],
                    1,
                    0
                ]);

                // 絶対値が小さいところは黒、それ以外は白
                map.setPaintProperty('stationGeomLabel', 'text-color', [
                    'interpolate',
                    ['linear'],
                    ['get', paintField],
                    -maxValue / 2.999, '#ffffff',
                    -maxValue / 3, '#222222',
                    maxValue / 3, '#222222',
                    maxValue / 2.999, '#ffffff'
                ]);
            } else if (value === 'distCycleOnly') {
                // 自転車が有効なら色分け
                // 自転車が無効ならグレー
                map.setPaintProperty('stationGeom', 'circle-color', [
                    'case',
                    ['boolean', ['get', 'cycleFlag'], false],
                    [
                        'interpolate',
                        ['linear'],
                        ['get', paintField],
                        0, palette[0],
                        maxValue / 10, palette[1],
                        maxValue * 2 / 10, palette[2],
                        maxValue * 3 / 10, palette[3],
                        maxValue * 4 / 10, palette[4],
                        maxValue / 2, palette[5]
                    ],
                    '#cccccc'
                ]);

                // 自転車が無効なら半径を小さく
                map.setPaintProperty('stationGeom', 'circle-radius', stationRadiusVaried);

                // 文字についても自転車が無効なら非表示
                map.setPaintProperty('stationGeomLabel', 'text-opacity', [
                    'case',
                    ['boolean', ['get', 'cycleFlag'], false],
                    1,
                    0
                ]);

                // 色分け
                map.setPaintProperty('stationGeomLabel', 'text-color', [
                    'case',
                    ['>', ['get', paintField], maxValue * 1 / 10],
                    '#ffffff', '#222222'
                ]);

            } else {
                map.setPaintProperty('stationGeom', 'circle-color', [
                    'interpolate',
                    ['linear'],
                    ['get', paintField],
                    0, palette[0],
                    maxValue / 10, palette[1],
                    maxValue * 2 / 10, palette[2],
                    maxValue * 3 / 10, palette[3],
                    maxValue * 4 / 10, palette[4],
                    maxValue / 2, palette[5]
                ]);
                
                map.setPaintProperty('stationGeom', 'circle-radius', stationRadiusUniform);

                map.setPaintProperty('stationGeomLabel', 'text-opacity', [
                    'case',
                    ['>', ['get', paintField], 0],
                    1, 0
                ]);
                map.setPaintProperty('stationGeomLabel', 'text-color', [
                    'case',
                    ['>', ['get', paintField], maxValue * 1 / 10],
                    '#ffffff', '#222222'
                ]);
            }

        }

        // 入力の変更による変更
        document.getElementById('cycleMinDist').addEventListener('input', () => {
            // 最大・最小の順番をキープ
            if (document.getElementById('cycleMinDist').value >= cycleMaxDist) {
                document.getElementById('cycleMinDist').value = cycleMaxDist - 1;
            }
            updateCyclingGraphLookup();
            updateView();
        });
        document.getElementById('cycleMaxDist').addEventListener('input', () => {
            // 最大・最小の順番をキープ
            if (document.getElementById('cycleMaxDist').value <= cycleMinDist) {
                document.getElementById('cycleMinDist').value = cycleMinDist + 1;
            }
            updateCyclingGraphLookup();
            updateView();
        });

        document.getElementById('extraTime').addEventListener('input', () => {
            extraTimeAllowed = Number(document.getElementById('extraTime').value);

            document.getElementById('extraTimeShow').textContent = `${extraTimeAllowed} [分]`;
            updateExtraTime();
        });

        // ----- 地図の初期化 -----
        updateStartingStation();

        // ----- レイヤーの追加 -----

        // 鉄道路線
        map.addLayer({
            'id': 'railway',
            'type': 'line',
            'source': 'railway',
            'layout': {
                'line-sort-key': 1,
            },
            'paint': {
                'line-color': '#888888',
                'line-opacity': 0.5,
                'line-width': 2,

            }
        }, 'pathChosen');

        // 駅
        map.addLayer({
            'id': 'stationGeom',
            'type': 'circle',
            'source': 'stationGeom',
            'layout': {
                'circle-sort-key': 3,
            },
            'paint': {
                'circle-radius': 0,
                'circle-color': '#ffffff',
            }
        }, 'pathChosen');

        // 駅ラベル
        map.addLayer({
            'id': 'stationGeomLabel',
            'type': 'symbol',
            'source': 'stationGeom',
            'layout': {
                'text-field': [
                    'to-string',
                    ['round', ['get', 'distDifference']]
                ],
                'text-size': [
                    'interpolate', ['linear'], ['zoom'],
                    9.995, 0,
                    10, 12,
                    14, 28,
                ],
                'text-font': [
                    'Open Sans Bold',
                    'Arial Unicode MS Bold',
                ],  
                'symbol-sort-key': 5
            },
            'paint': {
                'text-color': '#ffffff',
                'text-opacity': [
                    'case',
                    ['>', ['get', 'distCycle'], 0],
                    1, 0
                ]
            }
        }, 'pathChosen');

        setDisplayData();

        // eventListener
        document.getElementById('sourceStationForm').addEventListener('submit', (event) => {
            event.preventDefault();
            const inputValue = document.getElementById('sourceStation').value;
            if (stationList.includes(inputValue)) {
                // update view
                updateStartingStation();
            } else {
                alert('駅名を正しく入力してください。');
            }
        });

        // Change the values 
        document.getElementById('selectDataRadio').addEventListener('change', () => {
            setDisplayData();
        });

        // 右側のウィンドウを閉じると経路も消える
        document.getElementById('route-toggle').addEventListener('click', () => {

            // 表示を切り替え
            toggleDiv('route-toggle', 'route-contents', '経路情報を隠す', '経路情報を表示');

            const div = document.getElementById('route-contents');
            if (div.style.display === 'block') {
                // 経路を表示
                // 到着駅表示
                map.setFilter(
                    'clickedStation',
                    ['==', ['get', 'station_name'], clickedStationName]
                );
                map.setFilter(
                    'clickedStationLabel',
                    ['==', ['get', 'station_name'], clickedStationName]
                );               
                map.setPaintProperty('path', 'line-opacity', 1);
                map.setPaintProperty('pathChosen', 'line-opacity', 1);
            } else {
                // 色々と消す
                map.setFilter('clickedStation', false);
                map.setFilter('clickedStationLabel', false);
                map.setPaintProperty('path', 'line-opacity', 0);
                map.setPaintProperty('pathChosen', 'line-opacity', 0);                
                showCycleLayerFlag = false;
                map.setFilter('d_docks', false);
                map.setFilter('h_docks', false);
            }
        });

        // 駅にホバーすると現れるポップアップ
        map.on('mousemove', 'stationGeom', (e) => {
            map.getCanvas().style.cursor = 'pointer';
            // reset selection
            map.removeFeatureState({
                'source': 'stationGeom'
            });
            // get selected feature
            const selectedFeature = e.features[0];
            map.setFeatureState({
                source: 'stationGeom',
                id: selectedFeature.id,
            }, {
                'hover': true
            });
            const coordinates = selectedFeature.geometry.coordinates.slice();
            selectedStationName = selectedFeature.properties.station_name;

            const distCycleMins = selectedFeature.properties.distForceCycle;
            const distNoCycleMins = selectedFeature.properties.distNoCycle;
            const distDifferenceMins = distNoCycleMins - distCycleMins;
            let description = `<h3>${selectedStationName}</h3><hr>`;
            if (startingStationName === selectedStationName) {
                description += `<p>出発駅</p>`;
            } else {
                description += `
                    <p><strong>${startingStationName}</strong>からの所要時間</p>
                    <table class="popup">
                        <tr><td>自転車不使用</td><td>${Math.round(distNoCycleMins)}</td></tr>
                        <tr><td>自転車強制（最大${cycleMaxDist}km）</td><td id="popupDistCycleMins">${Math.round(distCycleMins)}</td></tr>
                        <tr><td>短縮時間</td><td id="popupDifferenceMins">${Math.round(distDifferenceMins)}</td></tr>
                    </table>
                `;
            }
            stationPopup.setLngLat(coordinates).setHTML(description).addTo(map);

            // 経路表示のアップデートはクリックのときに変更

            // updateRoutes();

        });
        // 離れたら削除
        map.on('mouseleave', 'stationGeom', () => {
            map.getCanvas().style.cursor = '';
            stationPopup.remove();
            map.removeFeatureState({
                'source': 'stationGeom'
            });
        });

        map.on('click', 'stationGeom', (e) => {
            // 自転車は消す
            showCycleLayerFlag = false;
            map.setFilter('d_docks', false);
            map.setFilter('h_docks', false);
            // save old clicked
            const oldClicked = clickedStationName;
            // get selected feature
            const clickedFeature = e.features[0];
            clickedStationName = clickedFeature.properties.station_name;

            // 出発駅をクリックした場合
            
            // 同じ駅を連続クリックで出発駅に指定
            if (oldClicked === clickedStationName) {
                document.getElementById('sourceStation').value = clickedStationName;
                updateStartingStation();
            } else {
                // スタートとゴールが違う場合は経路表示
                if (clickedStationName !== startingStationName) {
                    // 到着駅表示
                    map.setFilter(
                        'clickedStation',
                        ['==', ['get', 'station_name'], clickedStationName]
                    );
                    map.setFilter(
                        'clickedStationLabel',
                        ['==', ['get', 'station_name'], clickedStationName]
                    );
                    map.setFilter('path', null);
                    map.setFilter('pathChosen', null)
                    // 経路表示のアップデート
                    updateRoutes();
                    // map.flyTo({center: clickedFeature.geometry.coordinates});

                    // 経路ウィンドウの表示
                    if (document.getElementById('route-contents').style.display === 'none') {
                        toggleDiv('route-toggle', 'route-contents', '経路情報を隠す', '経路情報を表示');
                    }
                } else {
                    // スタートとゴールが同じ場合は表示をリセット
                    updateStartingStation();                    
                }
            }
        });

        // ドックにホバーすると現れるポップアップ
        map.on('mousemove', 'd_docks', (e) => {
            map.getCanvas().style.cursor = 'pointer';
            // reset selection
            map.removeFeatureState({
                'source': 'd_docks'
            });
            map.removeFeatureState({
                'source': 'h_docks'
            })
            // get selected feature
            const selectedFeature = e.features[0];
            map.setFeatureState({
                source: 'd_docks',
                id: selectedFeature.id,
            }, {
                'hover': true
            });
            const coordinates = selectedFeature.geometry.coordinates.slice();
            const prop = selectedFeature.properties
            const cycleOperator = 'dバイクシェア';
            const dockName = prop.name;
            const cycleAvailability = prop.availability;
            const dockAvailability = prop.dock_availability;
            const capacity = prop.calc_capacity;

            const description = `
                <h3>${dockName}</h3>
                <p><strong>${cycleOperator}</strong></p>
                <table id="class">
                    <tr>
                        <td>貸出可能台数</td>
                        <td>${cycleAvailability}</td>
                    </tr>
                    <tr>
                        <td>返却可能台数</td>
                        <td>${dockAvailability}</td>
                    </tr>
                    <tr>
                        <td>総ポート数</td>
                        <td>${capacity}</td>
                    </tr>
                </table>
            `;
            cyclePopup.setLngLat(coordinates).setHTML(description).addTo(map);
        });
        // ドックにホバーすると現れるポップアップ
        map.on('mousemove', 'h_docks', (e) => {
            map.getCanvas().style.cursor = 'pointer';
            // reset selection
            map.removeFeatureState({
                'source': 'd_docks'
            });
            map.removeFeatureState({
                'source': 'h_docks'
            })
            // get selected feature
            const selectedFeature = e.features[0];
            map.setFeatureState({
                source: 'h_docks',
                id: selectedFeature.id,
            }, {
                'hover': true
            });
            const coordinates = selectedFeature.geometry.coordinates.slice();
            const prop = selectedFeature.properties
            const cycleOperator = 'HELLO CYCLING';
            const dockName = prop.name;
            const cycleAvailability = prop.availability;
            const dockAvailability = prop.dock_availability;
            const capacity = prop.calc_capacity;

            const description = `
                <h3>${dockName}</h3><hr>
                <p><strong>${cycleOperator}</strong></p>
                <table class="popup">
                    <tr>
                        <td>貸出可能台数</td>
                        <td>${cycleAvailability}</td>
                    </tr>
                    <tr>
                        <td>返却可能台数</td>
                        <td>${dockAvailability}</td>
                    </tr>
                    <tr>
                        <td>総ポート数</td>
                        <td>${capacity}</td>
                    </tr>
                </table>
            `;
            cyclePopup.setLngLat(coordinates).setHTML(description).addTo(map);

        });

        // 離れたら削除
        map.on('mouseleave', 'd_docks', () => {
            map.getCanvas().style.cursor = '';
            cyclePopup.remove();
            map.removeFeatureState({
                'source': 'd_docks'
            });
        });        
        // 離れたら削除
        map.on('mouseleave', 'h_docks', () => {
            map.getCanvas().style.cursor = '';
            cyclePopup.remove();
            map.removeFeatureState({
                'source': 'h_docks'
            });
        });

        // hide loading screen
        document.getElementById('loading-screen').classList.add('hidden');
        setTimeout(() => {
            document.getElementById('loading-screen').style.display = 'None';
        }, 1000);

    });
});
