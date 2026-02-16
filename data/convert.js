import fs from 'fs/promises';
import topojson from 'topojson';


const input = JSON.parse(await fs.readFile('./data/swiss_stuffes.json', 'utf-8'));


for (const [key] of Object.entries(input.objects)) {
    const geojson = topojson.feature(input, input.objects[key]);
    await fs.writeFile(`./data/${key}.geojson`, JSON.stringify(geojson, null, 2));
}
