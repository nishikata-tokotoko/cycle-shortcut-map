// グローバル変数
let cycleMaxDist = Number(document.getElementById('cycleMaxDist').value);
let clickedStation = '';

// ---------- 地図関連 ----------

// 初期化
const map = new maplibregl.Map({
    container: 'map',
    style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
    center: [139.75, 35.69],
    zoom: 12
});

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

function createPieChart (selector, data, range, label)  {
    const margin = { top: 0, right: 0, bottom: 0, left: 0 },
    width = 120 - margin.left - margin.right,
    height = 120 - margin.top - margin.bottom;
    const radius = Math.min(width, height) / 2;

    let svg = d3.select(selector).select("svg");

    if (svg.empty()) {
        // Create the initial SVG container if it doesn't exist
        svg = d3.select(selector)
            .append("svg")
            .attr("width", width + margin.left + margin.right)
            .attr("height", height + margin.top + margin.bottom)
            .append("g")
            .attr("transform", `translate(${width / 2 + margin.top},${height / 2 + margin.left})`);

        svg.append("g").attr("class", "slices");
        svg.append("text")
            .attr("class", "label")
            .attr("text-anchor", "middle")
            .attr("dy", ".35em")
            .attr("font-weight", "bold");
    }

    const color = d3.scaleOrdinal()
        .range(range);

    const pie = d3.pie()
        .value(d => d[1]);

    const data_ready = pie(Object.entries(data));

    const arc = d3.arc()
        .innerRadius(40)
        .outerRadius(radius);

    const slices = svg.select(".slices")
        .selectAll("path")
        .data(data_ready);

    slices.enter()
        .append("path")
        .merge(slices)
        .transition()
        .duration(1000)
        .attr("d", arc)
        .attr("fill", d => color(d.data[0]))
        .style("opacity", 0.7);

    slices.exit().remove();

    svg.select(".label")
        .transition()
        .duration(1000)
        .text(label);
}

map.on('load', () => {
    Promise.all([
        fetch('doc_data/ksj_railways.geojson').then((response) => response.json()),
        fetch('doc_data/tokyo_stations_bet.geojson').then((response) => response.json()),        
        fetch('doc_data/hello_ports.geojson').then((response) => response.json()),        
        fetch('doc_data/docomo_ports.geojson').then((response) => response.json()),
        fetch('doc_data/edge_bet.geojson').then((response) => response.json()),
        
    ]).then(([railGeom, stationGeom, helloPorts, docomoPorts, edgeBet]) => {
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
        map.addSource('edgeBet', {
            type: 'geojson',
            data: edgeBet,
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
        
        // 駅リストを作成
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

        // H3 Indexを作成
        let gridDiskCache = new Map();
        const dDocksH3Index = buildH3Index(docomoPorts.features);
        const hDocksH3Index = buildH3Index(helloPorts.features);
        // 自転車のアップデート
        updateCycleStatus();
        setInterval(updateCycleStatus, 60000);

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
        });

        // 駅
        map.addLayer({
            'id': 'stationGeom',
            'type': 'circle',
            'source': 'stationGeom',
            'paint': {
                'circle-radius': 0,
                'circle-color': '#ffffff',
                'circle-stroke-color': '#DAA520',
                'circle-stroke-width': [
                    'case',
                    ['boolean', ['feature-state', 'hover'], false],
                    5,
                    0
                ],
            }
        });

        // 駅ラベル
        map.addLayer({
            'id': 'stationGeomLabel',
            'type': 'symbol',
            'source': 'stationGeom',
            'layout': {
                'text-field': ['get', 'station_name'],
                'text-size': [
                    'interpolate', ['linear'], ['zoom'],
                    9.995, 0,
                    10, 9,
                    14, 21,
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
        });
        map.setFilter('stationGeomLabel', false);        
        
        // 駅間のbetweenness
        map.addLayer({
            'id': 'edgeBet',
            'type': 'line',
            'source': 'edgeBet',
            'layout': {
                'line-cap': 'round',
                'line-join': 'round'
            },
            'paint': {
                "line-width": 0
            }
        }, 'stationGeom');

        // 選択された駅間のbetweenness
        map.addLayer({
            'id': 'edgeBetSelected',
            'type': 'line',
            'source': 'edgeBet',
            'paint': {
                "line-width": 0
            }
        }, 'stationGeom');
        // まずは隠す
        map.setFilter('edgeBetSelected', false);

        paintBet();

        // betweennessの値の設定
        function paintBet () {
            const betValue = ["get", String(cycleMaxDist), ["get", "betweenness"]];
            const totalCapacity = ['get', 'totalCapacity'];
            const potPerCap = [
                "/", 
                betValue, 
                ["+", totalCapacity, 10]
            ];
            // それぞれの最大値を計算
            const maxEdgeBet = edgeBet.features.reduce((max, feature) => {
                return feature.properties.betweenness[cycleMaxDist] > max ? feature.properties.betweenness[cycleMaxDist] : max;
            }, 0);
            const maxNodeBet = stationGeom.features.reduce((max, feature) => {
                return feature.properties.betweenness[cycleMaxDist] > max ? feature.properties.betweenness[cycleMaxDist] : max;
            }, 0);
            const maxTotalCap = Math.max(
                ...stationGeom.features.map((feature) => feature.properties.totalCapacity)
            );
            const maxPotPerCap = maxNodeBet / 100;

            const bluesPalette = ['#deebf7', '#4292c6', '#08306b'];
            const greensPalette = ['#f7fcf5', '#74c476','#00441b'];
            const purplesPalette = ['#dadaeb', '#807dba', '#3f007d'];
            const graysPalette = ['#eeeeee', '#969696', '#111111'];
            const rdYlBlPalette = ['#4575b4', '#ffffbf', '#d73027'];
            const palette = bluesPalette;
            const stPalette = purplesPalette;

            // 駅間の表示設定
            map.setLayoutProperty('edgeBet', 'line-sort-key', betValue);
            map.setPaintProperty('edgeBet', 'line-color', [
                // "case",
                // ["boolean", ["feature-state", "hover"], false],
                // '#DAA520',
                // [
                    "interpolate",
                    ["linear"],
                    ["sqrt", betValue],
                    0, palette[0],
                    Math.sqrt(maxEdgeBet) / 2, palette[1],
                    Math.sqrt(maxEdgeBet), palette[2]
                // ]
            ]);
            map.setPaintProperty('edgeBet', 'line-width', [
                'interpolate', ['linear'], ['zoom'],
                8, [
                    "interpolate",
                    ["linear"],
                    ["sqrt", betValue],
                    0, 0,
                    Math.sqrt(maxEdgeBet), 5
                ],
                14, [
                    "interpolate",
                    ["linear"],
                    ["sqrt", betValue],
                    0, 0,
                    Math.sqrt(maxEdgeBet), 40
                ]
            ]);
            // 表示するものをフィルター
            map.setFilter(
                'edgeBet',
                ['>', betValue, maxEdgeBet / 1000]
            );

            // 駅の表示設定
            // 駅で表示するデータの入力によって切り替え
            const dataChosen = document.getElementById('pickParamRadioForm')['pickParamRadio'].value;

            switch (dataChosen) {
                // ポテンシャルを表示する場合
                case 'cyclePotential':
                    map.setLayoutProperty('stationGeom', 'circle-sort-key', betValue);
                    map.setLayoutProperty('stationGeomLabel', 'symbol-sort-key', betValue);
                    map.setPaintProperty('stationGeom', 'circle-color', [
                        "interpolate",
                        ["linear"],
                        ["sqrt", betValue],
                        0, stPalette[0],
                        Math.sqrt(maxNodeBet) / 2, stPalette[1], 
                        Math.sqrt(maxNodeBet), stPalette[2]                                   
                    ]);
                    map.setPaintProperty('stationGeom', 'circle-radius', [
                        'interpolate', ['linear'], ['zoom'], 
                        8, [
                            'interpolate',
                            ['linear'], 
                            ['sqrt', betValue],
                            0, 1,
                            Math.sqrt(maxNodeBet), 5
                        ],
                        14, [
                            'interpolate',
                            ['linear'], 
                            ['sqrt', betValue],
                            0, 5,
                            Math.sqrt(maxNodeBet), 30
                        ]
                    ]);
                    // ラベルを非表示
                    map.setFilter('stationGeomLabel', false);                      
                    break;

                // ドック台数を表示
                case 'totalCapacity':
                    map.setLayoutProperty('stationGeom', 'circle-sort-key', betValue);
                    map.setLayoutProperty('stationGeomLabel', 'symbol-sort-key', betValue);
                    map.setPaintProperty('stationGeom', 'circle-color', [
                        "interpolate",
                        ["linear"],
                        totalCapacity,
                        0, greensPalette[0],
                        maxTotalCap / 2, greensPalette[1], 
                        maxTotalCap, greensPalette[2]                                   
                    ]);
                    map.setPaintProperty('stationGeom', 'circle-radius', [
                        'interpolate', ['linear'], ['zoom'], 
                        8, [
                            'interpolate',
                            ['linear'], 
                            totalCapacity,
                            0, 1,
                            maxTotalCap, 5
                        ],
                        14, [
                            'interpolate',
                            ['linear'], 
                            totalCapacity,
                            0, 5,
                            maxTotalCap, 30
                        ]
                    ]);
                    // ラベル
                    map.setLayoutProperty('stationGeomLabel', 'text-field', [
                        'to-string',
                        ['round', totalCapacity]
                    ]);
                    map.setFilter('stationGeomLabel', null);                
                    break;

                // // 供給量あたりキャパシティ
                // case 'potPerCap':
                //     map.setLayoutProperty('stationGeom', 'circle-sort-key', potPerCap);
                //     map.setLayoutProperty('stationGeomLabel', 'symbol-sort-key', potPerCap);
                //     map.setPaintProperty('stationGeom', 'circle-color', [
                //         "interpolate",
                //         ["linear"],
                //         ["sqrt", potPerCap],
                //         0, rdYlBlPalette[0],
                //         Math.sqrt(maxPotPerCap) / 2, rdYlBlPalette[1], 
                //         Math.sqrt(maxPotPerCap), rdYlBlPalette[2]                                   
                //     ]);
                //     map.setPaintProperty('stationGeom', 'circle-radius', [
                //         'interpolate', ['linear'], ['zoom'], 
                //         8, [
                //             'interpolate',
                //             ['linear'], 
                //             ['sqrt', potPerCap],
                //             0, 1,
                //             Math.sqrt(maxPotPerCap), 5
                //         ],
                //         14, [
                //             'interpolate',
                //             ['linear'], 
                //             ['sqrt', potPerCap],
                //             0, 5,
                //             Math.sqrt(maxPotPerCap), 30
                //         ]
                //     ]);
                //     map.setLayoutProperty('stationGeomLabel', 'text-field', [
                //         'to-string',
                //         ['round', potPerCap]
                //     ]);
                //     map.setFilter('stationGeomLabel', null);                
                //     break;                
            }
        }

        // Popup
        const edgePopup = new maplibregl.Popup({
            closeButton: false,
            closeOnClick: false,
            anchor: 'top-left',
            offset: 5            
        });
        const nodePopup = new maplibregl.Popup({
            closeButton: false,
            closeOnClick: false,
            anchor: 'bottom-left',
            offset: 5
        });

        // 駅にホバー
        map.on('mousemove', 'stationGeom', (e) => {
            map.getCanvas().style.cursor = 'pointer';
            map.removeFeatureState({
                'source': 'stationGeom'
            });

            // 選ばれたやつ
            const selectedFeature = e.features[0];
            map.setFeatureState({
                source: 'stationGeom',
                id: selectedFeature.id
            }, {
                'hover': true
            });

            const coordinates = selectedFeature.geometry.coordinates.slice(); 
            const stationName = selectedFeature.properties.station_name;
            let betCent = selectedFeature.properties.betweenness;
            if (typeof betCent === 'string') {
                betCent = JSON.parse(betCent);
            }

            const description = `
                <h3>${stationName}</h3>
                <p>自転車ポテンシャル</p><hr>
                <table class="popup">
                    <tr><th>最大距離</th><th>ポテンシャル</th></tr>
                    <tr><th>4 km</th><th>${Math.round(betCent["4"])} 人/日</th></tr>
                    <tr><th>6 km</th><th>${Math.round(betCent["6"])} 人/日</th></tr>
                    <tr><th>8 km</th><th>${Math.round(betCent["8"])} 人/日</th></tr>
                    <tr><th>10 km</th><th>${Math.round(betCent["10"])} 人/日</th></tr>                    
                </table>
            `;
            nodePopup.setLngLat(coordinates).setHTML(description).addTo(map);
        });

        // 離れたら削除
        map.on('mouseleave', 'stationGeom', () => {
            map.getCanvas().style.cursor = '';
            nodePopup.remove();
            map.removeFeatureState({
                'source': 'stationGeom'
            });
        });
        
        // エッジにホバー
        map.on('mousemove', 'edgeBet', (e) => {
            map.getCanvas().style.cursor = 'pointer';
            map.removeFeatureState({
                'source': 'edgeBet'
            });
            // 選ばれたやつ
            const selectedFeature = e.features[0];
            map.setFeatureState({
                source: 'edgeBet',
                id: selectedFeature.id
            }, {
                'hover': true
            });
            
            const coordinates = [e.lngLat.lng, e.lngLat.lat];
            const prop = selectedFeature.properties;
            const source = prop.source;
            const target = prop.target;
            let betCent = selectedFeature.properties.betweenness;
            const length = Math.round(prop.length);
            if (typeof betCent === 'string') {
                betCent = JSON.parse(betCent);
            }

            const description = `
                <h3>${source}ー${target}</h3>
                <p>距離 | <strong>${length} m</strong></p>
                <hr>
                <table class="popup">
                    <tr><th>最大距離</th><th>ポテンシャル</th></tr>
                    <tr><th>4 km</th><th>${Math.round(betCent["4"])} 人/日</th></tr>
                    <tr><th>6 km</th><th>${Math.round(betCent["6"])} 人/日</th></tr>
                    <tr><th>8 km</th><th>${Math.round(betCent["8"])} 人/日</th></tr>
                    <tr><th>10 km</th><th>${Math.round(betCent["10"])} 人/日</th></tr>                    
                </table>
            `;
            edgePopup.setLngLat(coordinates).setHTML(description).addTo(map);
        });

        // 離れたら削除
        map.on('mouseleave', 'edgeBet', () => {
            map.getCanvas().style.cursor = '';
            edgePopup.remove();
            map.removeFeatureState({
                'source': 'edgeBet'
            });
        });

        // 駅のサイクリングポテンシャルを更新
        function updateCyclingPotential(stationName) {
            document.getElementById('potentialHead').textContent = `${stationName}駅 ポテンシャル情報`
            // 情報を取得
            const selectedFeature = stationGeom.features.filter((feature) => feature.properties.station_name === stationName)[0];

            let betCent = selectedFeature.properties.betweenness;
            if (typeof betCent === 'string') {
                betCent = JSON.parse(betCent);
            }
            // データを整理
            const data = [
                { distance: '4 km', potential: Math.round(betCent["4"]) },
                { distance: '6 km', potential: Math.round(betCent["6"]) },
                { distance: '8 km', potential: Math.round(betCent["8"]) },
                { distance: '10 km', potential: Math.round(betCent["10"]) }
            ];
            // const tableHTML = `
            //     <p>${stationName}駅の自転車最大距離別ポテンシャル</p>
            //     <table id="stationPotentialTable">
            //         <tr><th>最大距離</th><th>ポテンシャル</th></tr>
            //         <tr><th>4 km</th><th>${betCent["4"]}</th></tr>
            //         <tr><th>6 km</th><th>${betCent["6"]}</th></tr>
            //         <tr><th>8 km</th><th>${betCent["8"]}</th></tr>
            //         <tr><th>10 km</th><th>${betCent["10"]}</th></tr>                    
            //     </table>
            // `;
            // document.getElementById('stationPotential').innerHTML = tableHTML;
            
            const margin = { top: 10, right: 20, bottom: 20, left: 40 },
                width = 330 - margin.left - margin.right,
                height = 120 - margin.top - margin.bottom;
            
            let svg = d3.select("#stationPotential").select("svg");

            if (svg.empty()) {
                // Create the initial SVG container if it doesn't exist
                svg = d3.select("#stationPotential")
                    .append("svg")
                    .attr("width", width + margin.left + margin.right)
                    .attr("height", height + margin.top + margin.bottom)
                    .append("g")
                    .attr("transform", `translate(${margin.left},${margin.top})`);
            
                svg.append("g")
                    .attr("class", "x-axis")
                    .attr("transform", `translate(0,${height})`);
            
                svg.append("g")
                    .attr("class", "y-axis");
            }
            
            const x = d3.scaleLinear()
                .domain([0, d3.max(data, d => d.potential)])
                .range([0, width]);
            
            const y = d3.scaleBand()
                .range([0, height])
                .domain(data.map(d => d.distance))
                .padding(.1);
            
            svg.select(".x-axis")
                .transition()
                .duration(1000)
                .attr("font-weight", "bold")
                .call(d3.axisBottom(x).ticks(5));
            
            svg.select(".y-axis")
                .transition()
                .duration(1000)
                .attr("font-weight", "bold")
                .call(d3.axisLeft(y));
            
            const bars = svg.selectAll(".bar")
                .data(data, d => d.distance);
            
            bars.enter()
                .append("rect")
                .attr("class", "bar")
                .attr("x", x(0))
                .attr("y", d => y(d.distance))
                .attr("width", 0)
                .attr("height", y.bandwidth())
                .attr("fill", "#156082")
                .merge(bars)
                .transition()
                .duration(1000)
                .attr("width", d => x(d.potential));
            
            bars.exit().remove();
            
            // Add data labels
            const labels = svg.selectAll(".label")
                .data(data, d => d.distance);
            
            labels.enter()
                .append("text")
                .attr("class", "label")
                .attr("x", d => x(0) + 5)
                .attr("y", d => y(d.distance) + y.bandwidth() / 2 + 4)
                .attr("font-size", "10px")
                .attr("fill", "white")
                .attr("font-weight", "bold")
                .merge(labels)
                .transition()
                .duration(1000)
                .attr("x", d => x(0) + 5)
                .attr("y", d => y(d.distance) + y.bandwidth() / 2 + 4)
                .text(d => d.potential);
            
            labels.exit().remove();

        }

        // 駅から出るポテンシャルを取得
        function getHighPotentialLinks(stationName, numLinks) {
            // 関係あるリンクを抽出
            const betLinks = edgeBet.features.filter((feature) => (feature.properties.source === stationName) || (feature.properties.target === stationName));
            betLinks.sort((a, b) => {
                const aBetweenness = typeof a.properties.betweenness === 'string' ? JSON.parse(a.properties.betweenness)[cycleMaxDist] : a.properties.betweenness[cycleMaxDist];
                const bBetweenness = typeof b.properties.betweenness === 'string' ? JSON.parse(b.properties.betweenness)[cycleMaxDist] : b.properties.betweenness[cycleMaxDist];
                return bBetweenness - aBetweenness;
            });
            // 上位をフィルター
            const showLinks = betLinks.slice(0, numLinks);

            // tableのHTMLを生成
            let tableHTML = `
                <p>クリックすると到着駅の詳細情報を表示します。</p>
                <table class="linkBetTable" id="linkBetTable">
                    <tr><th colspan="2">自転車リンク発着駅</th><th>距離[m]</th><th>ポテンシャル［人/日］</th></tr>
            `
            showLinks.forEach((feature) => {
                const otherStation = feature.properties.source === stationName ? feature.properties.target : feature.properties.source;
                const betValue = typeof feature.properties.betweenness === 'string' ? JSON.parse(feature.properties.betweenness)[cycleMaxDist] : feature.properties.betweenness[cycleMaxDist];
                const length = Math.round(feature.properties.length);

                const tableRow = `
                    <tr data-other-station="${otherStation}">
                        <td>${stationName}</td>
                        <td>${otherStation}</td>
                        <td>${length}</td>
                        <td>${Math.round(betValue)}</td>
                    </tr>
                `
                tableHTML += tableRow;
            })
            tableHTML += `</table>`;

            // 表示を更新
            document.getElementById('highPotentialLinks').innerHTML = tableHTML;
            // return tableHTML;

            // 生成した表に対して、駅をクリックすればそっちの情報に飛ぶようにeventListenerを設定
            document.getElementById('linkBetTable').addEventListener('click', (event) => {

                clickedStation = event.target.closest('tr').dataset.otherStation;
                document.getElementById('potentialStation').value = clickedStation;

                // 新駅に飛ぶ
                const newStation = stationGeom.features.filter((feature) => feature.properties.station_name === clickedStation)[0];
                map.flyTo({
                    center: newStation.geometry.coordinates,
                    // zoom: 11,
                });
                updateCyclingPotential(clickedStation);
                getHighPotentialLinks(clickedStation, numLinks);
                showCycles(clickedStation);
            });

        }

        // 駅に近いサイクルポート情報を取得
        function showCycles(stationName) {
            // 情報を取得
            const selectedFeature = stationGeom.features.filter((feature) => feature.properties.station_name === stationName)[0];
            
            const stationH3 = selectedFeature.properties.h3_index;
            // 9個分 = 約500m分シェアサイクルについて集計
            const gridDisk = h3.gridDisk(stationH3, 9);
            const aggAvail = aggCycleStatus(gridDisk, hDocksH3Index, dDocksH3Index);

            if (aggAvail.total.numPorts === 0) {
                const description = `<p>${stationName}駅付近にサイクリングポートはありません。</p>`
                // 表示を更新
                document.getElementById('cycleDockInfo').innerHTML = description;                
            } else {
                // プレースホルダー
                const cycleTable = `
                    <p>リアルタイム利用可能台数 / ドック数</p>
                    <table id="cyclePortTable">
                        <tr>
                            <th>dバイクシェア</th><th>HELLO CYCLING</th>
                        </tr>
                        <tr>
                            <td><div id="docomoPie"></div></td>
                            <td><div id="helloPie"></div></td>
                        </tr>
                        <tr>
                            <td id="docomoLabel"></td>
                            <td id="helloLabel"></td>
                        </tr>
                    </table>
                `;
                document.getElementById('cycleDockInfo').innerHTML = cycleTable;
                                
                const docomoData = {
                    available: aggAvail.docomo.availability,
                    unavailable: aggAvail.docomo.dockAvailability
                };
                
                const helloData = {
                    available: aggAvail.hello.availability,
                    unavailable: aggAvail.hello.dockAvailability
                };
                
                // Clear previous charts
                // d3.select("#docomoPie").selectAll("*").remove();
                // d3.select("#helloPie").selectAll("*").remove();
                
                // Create pie charts
                createPieChart("#docomoPie", docomoData, ['#dd0000', '#660000'], `${aggAvail.docomo.availability} / ${aggAvail.docomo.calcCapacity}`);
                createPieChart("#helloPie", helloData, ['#ffdd00', '#888800'], `${aggAvail.hello.availability} / ${aggAvail.hello.calcCapacity}`);

                // ドック台数表示
                document.getElementById('docomoLabel').innerHTML = `ポート数 | <strong>${aggAvail.docomo.numPorts}</strong>ヶ所`;document.getElementById('helloLabel').innerHTML = `ポート数 | <strong>${aggAvail.hello.numPorts}</strong>ヶ所`;

            };
        }
        
        // 駅単位で集計範囲を変更して再集計
        function updateAggCycleStatus() {
            const maxDistInput = 9;
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
            console.log('Updated Cycle Status');
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

        map.on('click', 'stationGeom', (e) => {
            const selectedFeature = e.features[0];
            clickedStation = selectedFeature.properties.station_name;
            document.getElementById('potentialStation').value = clickedStation;
            const coords = selectedFeature.geometry.coordinates.slice();
            map.flyTo({
                center: coords
            });
            updateCyclingPotential(clickedStation);
            getHighPotentialLinks(clickedStation, 5);
            showCycles(clickedStation);

            // 経路ウィンドウの表示
            if (document.getElementById('overlay-right-contents').style.display === 'none') {
                toggleDiv('route-toggle', 'overlay-right-contents', '隠す', '詳細を表示');
            }
        })

        // eventListener
        document.getElementById('potentialStationForm').addEventListener('submit', (event) => {
            event.preventDefault();
            const inputValue = document.getElementById('potentialStation').value;
            if (stationList.includes(inputValue)) {
                // update view
                clickedStation = document.getElementById('potentialStation').value;

                // move to station
                const newStation = stationGeom.features.filter((feature) => feature.properties.station_name === clickedStation)[0];
                map.flyTo({
                    center: newStation.geometry.coordinates,
                });
                updateCyclingPotential(clickedStation);
                getHighPotentialLinks(clickedStation, 5);
                showCycles(clickedStation);
    
                // 経路ウィンドウの表示
                if (document.getElementById('overlay-right-contents').style.display === 'none') {
                    toggleDiv('route-toggle', 'overlay-right-contents', '隠す', '詳細を表示');
                }               

            } else {
                alert('駅名を正しく入力してください。');
            }
        });


        // イベントリスナーの追加

        // 最長距離の編集
        document.getElementById('cycleMaxDist').addEventListener('input', () => {
            // 値の編集
            cycleMaxDist = Number(document.getElementById('cycleMaxDist').value);
            document.getElementById('cycleMaxDistShow').textContent = `${cycleMaxDist} [km]`;
            
            paintBet();
            getHighPotentialLinks(clickedStation, 5);
        });

        // ラジオボタンの操作
        document.getElementById('pickParamRadioForm').addEventListener('input', () => {
            paintBet();
        })
        
        // hide loading screen
        document.getElementById('loading-screen').classList.add('hidden');
        setTimeout(() => {
            document.getElementById('loading-screen').style.display = 'None';
        }, 1000);

    });
});
