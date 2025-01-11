// // ファイルの読み込み
// async function loadMultipleJSONFiles(filePaths) {
//     const promises = filePaths.map(path => fetch(path).then(response => response.json()));

//     try {
//         const results = await Promise.all(promises);
//         return results;
//     } catch (error) {
//         console.error('Error loading JSON files:', error);
//     }
// }

// // 検索機能
// const files = ['tokyo_graph.json', 'tokyo_stations.json'];
// loadMultipleJSONFiles(files).then(([graph, stations]) => {
//     console.log(graph);
//     console.log(stations);

//     // イベントリスナー
//     document.getElementById('searchButton').addEventListener('click', () => searchButton(graph, stations));

// });

// // 検索ボタン押下時のイベントリスナー
// function searchButton(G, stations) {
//     // 表示
//     document.getElementById('route').innerHTML = "<p>計算中……</p>";

//     // input values
//     source = document.getElementById('source').value;
//     target = document.getElementById('target').value;
//     let G_new = setStations(G, stations, source, target);
//     graphLookup = buildGraphLookup(G_new);
//     // calculate shortest path
//     let shortestPathDict = dijkstra(G_new, source, target, graphLookup);

//     let returnDuration = shortestPathDict.distance;
//     let shortestPath = shortestPathDict.path;

//     console.log(returnDuration);
//     console.log(shortestPath);

//     let shortestPathShow = shortestPath.join('<br>')

//     // update results
//     document.getElementById('duration').innerHTML = "<p>所要時間： " + Math.ceil(returnDuration) + "分</p>";
//     document.getElementById('route').innerHTML = "<p>経路： " + shortestPathShow + "</p>";
// }

// // ネットワークの編集
// function setStations(G, stations, source, target) {
//     G_new = structuredClone(G);
//     // ノードの追加
//     sourceGroupNode = {
//         'id': source,
//         'node_type': 'station_group'
//     };
//     targetGroupNode = {
//         'id': target,
//         'node_type': 'station_group'
//     };
//     G_new.nodes.push(sourceGroupNode, targetGroupNode);

//     // エッジの追加
//     sourceNodes = stations[source].station_nodes;
//     targetNodes = stations[target].station_nodes;
//     for (let i = 0; i < sourceNodes.length; i++) {
//         linkObj = {
//             'source': source,
//             'target': sourceNodes[i],
//             'duration': 0.001,
//             'link_type': 'station_group'
//         };
//         G_new.links.push(linkObj);
//     };
//     for (let i = 0; i < targetNodes.length; i++) {
//         linkObj = {
//             'source': targetNodes[i],
//             'target': target,
//             'duration': 0.001,
//             'link_type': 'station_group'
//         };
//         G_new.links.push(linkObj);
//     };

//     return G_new;
// }
function createPieChart (selector, data, range, label, size = 120, innerRadius = 40)  {
    const margin = { top: 0, right: 0, bottom: 0, left: 0 },
    width = size - margin.left - margin.right,
    height = size - margin.top - margin.bottom;
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
        .innerRadius(innerRadius)
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

// グラフのインデックス
function buildGraphLookup(G) {
    let graphLookup = {};
    for (let link of G.links) {
        if (!graphLookup[link.source]) {
            graphLookup[link.source] = [];
        }
        graphLookup[link.source].push(link);
    }
    return graphLookup;
}

// Heap
class MinHeap {
    constructor() {
        this.heap = [];
    }

    // Add a new element to the heap
    add(element) {
        this.heap.push(element);
        this.bubbleUp();
    }

    // Remove and return the smallest element
    poll() {
        if (this.heap.length === 1) return this.heap.pop();
        const min = this.heap[0];
        this.heap[0] = this.heap.pop();
        this.bubbleDown();
        return min;
    }

    // Check if the heap is empty
    isEmpty() {
        return this.heap.length === 0;
    }

    // Move the last element up to maintain heap order
    bubbleUp() {
        let index = this.heap.length - 1;
        while (index > 0) {
            let parentIndex = Math.floor((index - 1) / 2);
            if (this.heap[index].distance >= this.heap[parentIndex].distance) break;
            [this.heap[index], this.heap[parentIndex]] = [this.heap[parentIndex], this.heap[index]];
            index = parentIndex;
        }
    }

    // Move the first element down to maintain heap order
    bubbleDown() {
        let index = 0;
        const length = this.heap.length;
        while (true) {
            let leftChildIndex = 2 * index + 1;
            let rightChildIndex = 2 * index + 2;
            let smallest = index;

            if (leftChildIndex < length && this.heap[leftChildIndex].distance < this.heap[smallest].distance) {
                smallest = leftChildIndex;
            }
            if (rightChildIndex < length && this.heap[rightChildIndex].distance < this.heap[smallest].distance) {
                smallest = rightChildIndex;
            }
            if (smallest === index) break;

            [this.heap[index], this.heap[smallest]] = [this.heap[smallest], this.heap[index]];
            index = smallest;
        }
    }
}

// 最短経路探索
function dijkstra(G, source, target, graphLookup) {
    const queue = new MinHeap();
    let distances = { [source]: 0 };
    let parents = { [source]: null };
    let visited = new Set();

    queue.add({ node: source, distance: 0 });

    while (!queue.isEmpty()) {
        const { node, distance } = queue.poll();

        if (visited.has(node)) continue;
        visited.add(node);

        if (node === target) break;

        const neighbors = graphLookup[node] || [];
        for (let { target: neighbor, duration } of neighbors) {
            if (visited.has(neighbor)) continue;

            const newDistance = distance + duration;
            if (newDistance < (distances[neighbor] || Infinity)) {
                distances[neighbor] = newDistance;
                parents[neighbor] = node;
                queue.add({ node: neighbor, distance: newDistance });
            }
        }
    }

    let path = [];
    let currentNode = target;
    while (currentNode) {
        // 'AC+'を取り除く
        const fixedId = currentNode.replace(`AC+`, ``);
        path.unshift(fixedId);
        currentNode = parents[currentNode];
    }

    return {
        distance: distances[target] || Infinity,
        path: distances[target] !== undefined ? path : []
    };
}

// 1つの駅からの到達圏を分析
// 最短経路探索
function dijkstra_multiple(G, source, targets, graphLookup) {
    const queue = new MinHeap();
    let distances = { [source]: 0 };
    let parents = { [source]: null };
    let visited = new Set();

    queue.add({ node: source, distance: 0 });

    // Initialize target distances and paths
    let targetDistances = {};
    let targetPaths = {};

    while (!queue.isEmpty()) {
        const { node, distance } = queue.poll();

        if (visited.has(node)) continue;
        visited.add(node);

        // Check if the node is one of the targets
        if (targets.includes(node)) {

            // remove 'AC+' and '_target' from returned key
            const nodeKey = node.replace(`AC+`, ``).replace('_target', '');

            targetDistances[nodeKey] = distance;
            targetPaths[nodeKey] = [];

            let currentNode = node;
            while (currentNode) {
                // 'AC+'を取り除く
                const fixedId = currentNode.replace(`AC+`, ``);
                targetPaths[nodeKey].unshift(fixedId);
                currentNode = parents[currentNode];
            }

            // Remove the target from the list once we have found the path
            targets = targets.filter(target => target !== node);
            // If all targets are found, break the loop
            if (targets.length === 0) break;
        }

        const neighbors = graphLookup[node] || [];
        for (let { target: neighbor, duration } of neighbors) {
            if (visited.has(neighbor)) continue;

            const newDistance = distance + duration;
            if (newDistance < (distances[neighbor] || Infinity)) {
                distances[neighbor] = newDistance;
                parents[neighbor] = node;
                queue.add({ node: neighbor, distance: newDistance });
            }
        }
    }

    // Return distances and paths for all targets
    return {
        duration: targetDistances,
        paths: targetPaths
    };
}


// 乗り換え経路をdictに整理
function parsePath(G, path) {

    // 駅データを返す関数
    function getNodeData(id) {
        return G.nodes.filter(node => node.id === id)[0];
    }

    // ノードを追加する関数
    function addNode(node, pathData, thruServiceFlag = false) {

        // データの生成
        let stationName = node.station_name;
        const nodeGeom = [node.x, node.y];
        let nodeData = {
            'type': 'node',
            'nodeType': node.node_type,
            'stationName': stationName,
            'duration': 0,
            'coordinates': nodeGeom
        };
        if (thruServiceFlag) {
            nodeData.nodeType = 'thru_service';
            nodeData.duration = 1;
        }
        // ノードが連続になる場合はくっつける
        if (pathData.length > 0) {
            const lastNode = pathData[pathData.length - 1];
            if (lastNode.type === 'node') {
                lastNode.stationName = node.station_name;
                lastNode.nodeType = 'transfer';
                if (thruServiceFlag) {
                    lastNode.duration += 1;
                }
            } else {
                pathData.push(nodeData);
            }
        } else {
            pathData.push(nodeData);
        }
    }

    function updateEdge(edge, pathData, geometry) {
        const lastPath = pathData[pathData.length - 1];
        if (lastPath.type !== 'edge') {
            let edgeData = {
                'type': 'edge',
                'edgeType': edge.link_type,
                'duration': edge.duration,
                // 'coordinates': [],
            }
            if (edge.link_type === 'train') {
                edgeData['railway'] = edge.railway;
                edgeData['trainType'] = edge.train_type;
                edgeData['direction'] = edge.direction;
            }
            if (edge.link_type === 'cycle' || edge.link_type === 'walk') {
                edgeData['distance'] = edge.distance;
            }
            pathData.push(edgeData);

            // nodeのcoordinatesを取得
            const sourceNode = getNodeData(edge.source);
            const sourceCoords = [sourceNode.x, sourceNode.y];
            const targetNode = getNodeData(edge.target);
            const targetCoords = [targetNode.x, targetNode.y];

            // geometryを追加
            let geomData = {
                'type': 'Feature',
                'geometry': {
                    'type': 'LineString',
                    'coordinates': [
                        sourceCoords,
                        targetCoords
                    ]
                },
                'properties': edgeData
            };
            geometry.push(geomData);
            
        } else {
            // console.log(lastPath);
            // 前がエッジだった場合は所要時間を追加
            lastPath.duration += edge.duration;
            // geometry[geometry.length - 1].properties.duration += edge.duration;

            // 最後の座標を追加
            const targetNode = getNodeData(edge.target);
            const targetCoords = [targetNode.x, targetNode.y];
            geometry[geometry.length - 1].geometry.coordinates.push(targetCoords);
        }
    }
    
    let pathData = [];
    let totalDuration = 0;
    let geometry = [];
    for (let i = 0; i < (path.length - 1); i++) {
        // 該当リンクの抽出
        const start = path[i];
        const end = path[i + 1];
        let edgeData = G.links.filter(link => (link.source === start && link.target === end))[0];

        // 総所要時間を追加
        totalDuration += edgeData.duration;

        // 経路データを作成していく
        // 基本は、乗車時にエッジデータ、降車時にノードデータを作る。
        switch (edgeData.link_type) {
            case 'source':
                addNode(getNodeData(end), pathData);
                break;
            case 'on_off':
                if (edgeData.on_off === 'off') {
                    addNode(getNodeData(end), pathData);
                } else {
                    // 乗車時は平均待ち時間を追加
                    pathData[pathData.length - 1].duration += edgeData.duration;
                }                
                break;
            case 'cycle':
            case 'walk':
            case 'cycle_station':
                updateEdge(edgeData, pathData, geometry);
                addNode(getNodeData(end), pathData);                
                break;
            case 'train':
                updateEdge(edgeData, pathData, geometry);
                break;
            case 'transfer':
                if (edgeData.same_station === 0) {
                    updateEdge(edgeData, pathData, geometry);
                    addNode(getNodeData(end), pathData);
                } else {
                    pathData[pathData.length - 1].duration += edgeData.duration;

                    // geometryを追加
                    // nodeのcoordinatesを取得
                    const sourceNode = getNodeData(edgeData.source);
                    const sourceCoords = [sourceNode.x, sourceNode.y];
                    const targetNode = getNodeData(edgeData.target);
                    const targetCoords = [targetNode.x, targetNode.y];
                    let geomData = {
                        'type': 'Feature',
                        'geometry': {
                            'type': 'LineString',
                            'coordinates': [
                                sourceCoords,
                                targetCoords
                            ]
                        },
                        'properties': {                 
                            'type': 'edge',
                            'edgeType': edgeData.link_type,
                            'duration': edgeData.duration,}
                    };
                    geometry.push(geomData);

                }
                break;
            case 'thru_service':
                addNode(getNodeData(end), pathData, true);
                break;
            case 'connection':
                break;            
            case 'target':
                break;
        }
    }
    console.log(pathData);
    // console.log('Total duration: ', totalDuration);

    return {
        'pathData': pathData,
        'totalDuration': totalDuration,
        'geometry': geometry
    };
}

function displayPath (parsedPath, railData, trainType, stationGeom) {
    const pathDict = parsedPath.pathData;
    const totalDuration = parsedPath.totalDuration;

    let resultTable = `<table class="pathTable">`;
    for (let i = 0; i < pathDict.length; i++) {
        const pathSeg = pathDict[i];
        if (pathSeg.type === 'node') {
            let durationStr = ''
            if (Math.round(pathSeg.duration) !== 0) {
                durationStr = `${Math.round(pathSeg.duration)}分`
            }
            // 自転車の場合はサイクルポートを追加
            let stationDisp = pathSeg.stationName;

            // サイクルポートの有無を確認
            const stationData = stationGeom.features.filter((feature) => feature.properties.station_name === pathSeg.stationName)[0].properties;
            const cycleFlag = (stationData.totalNumPorts > 0)
            if (pathSeg.nodeType === 'cycle_on' || pathSeg.nodeType === 'cycle_off') {
                stationDisp += `駅周辺 サイクルポート`;
                if (cycleFlag) {
                    stationDisp += `<div class="cycleDetail">※クリックして場所を表示</div>`;
                    // stationDisp += `
                    // <div class="cycleDetail">
                    //     現在の利用状況
                    //     <table>
                    //         <tr><td><div id="dChart_${i}"></div></td><td><div id="hChart_${i}"></div></td></tr>
                    //     </table>
                    // </div>`;
                    // // データを取得
                    // const data = {
                    //     docomo: {
                    //         available: stationData.docomoAvailableCycles,
                    //         unavailable: stationData.docomoAvailableDocks
                    //     },
                    //     hello: {
                    //         available: stationData.helloAvailableCycles,
                    //         unavailable: stationData.helloAvailableDocks
                    //     },                        
                    // }
                    // console.log(data);
                    // createPieChart(`dChart_${i}`, data.docomo, ['#dd0000', '#660000'], `${data.docomo.availabile} / ${data.docomo.unavailable}`, 80, 30);
                    // createPieChart(`hChart_${i}`, data.hello, ['#ffdd00', '#888800'], `${data.hello.availabile} / ${data.docomo.hello}`, 80, 30);

                } else {
                    stationDisp += `<div class="cycleDetail">※現在は付近にサイクルポート無し</div>`;
                }
            }
            if (pathSeg.nodeType === 'thru_service') {
                stationDisp = '（直通）' + stationDisp;
            }                                           
            resultTable += `
                <tr class="pathTableNode" data-station-name="${pathSeg.stationName}" data-node-type="${pathSeg.nodeType}">
                    <td>${durationStr}</td>
                    <td>●</td>
                    <td>${stationDisp}</td>
                </tr>
            `
        } else {
            if (pathSeg.edgeType === 'train') {
                const railway = railData.filter(rail => rail['railway_id'] === pathSeg.railway)[0];
                const trainTypeTemp = trainType.filter(type => type['owl:sameAs'] === pathSeg.trainType)[0]['dc:title']

                let durationStr = '';
                if (Math.round(pathSeg.duration) !== 0) {
                    durationStr = `${Math.round(pathSeg.duration)}分`
                }
                
                resultTable += `
                    <tr class="pathTableEdge trainEdge">
                        <td>${durationStr}</td>
                        <td>|</td>
                        <td>${railway.operator_name.ja}${railway.railway_name.ja} ${trainTypeTemp}</td>
                    </tr>                                    
                `
            } else if (pathSeg.edgeType === 'cycle') {
                resultTable += `
                    <tr class="pathTableEdge cycleEdge">
                        <td>${Math.round(pathSeg.duration)}分</td>
                        <td>|</td>
                        <td>自転車 (${Math.round(pathSeg.distance)} m)</td>
                    </tr>                                    
                `         
            } else {
                const edgeTypeDict = {
                    'cycle_station': '徒歩',
                    'walk': '徒歩',
                    'cycle': '自転車',
                    'transfer': '乗り換え'
                }
                resultTable += `
                    <tr class="edge">
                        <td>${Math.round(pathSeg.duration)}分</td>
                        <td>|</td>
                        <td>${edgeTypeDict[pathSeg.edgeType]}</td>
                    </tr>                                    
                `                                    
            }
        }
    }
    resultTable += `</table>`;
    
    return {
        'pathTable': resultTable,
        'totalDuration': totalDuration
    }
}


// エクスポート
export { buildGraphLookup, dijkstra, dijkstra_multiple, parsePath, displayPath };