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

export { fetchGBFS, updateFromAPI, updateAvailability, buildH3Index };