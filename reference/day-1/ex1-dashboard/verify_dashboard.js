// Runs the page's CORE logic block in Node and prints JSON (compared with verify_dashboard.py).  node verify_dashboard.js
const fs = require("fs"), html = fs.readFileSync(__dirname + "/index.html", "utf8");
const core = html.match(/<script id="core">([\s\S]*?)<\/script>/)[1];
const m = {exports: {}}; new Function("module", core)(m);
const {parseCSV, prepare, inRange, monthly, worstWeeks, summary} = m.exports;
const csv = fs.readFileSync(process.argv[2] || __dirname + "/../../../day-1/ex1-dashboard/munich_weather_2025.csv", "utf8");
const rows = prepare(parseCSV(csv));
const [a, b] = [+(process.argv[3] || 1), +(process.argv[4] || 12)], sel = inRange(rows, a, b);
console.log(JSON.stringify({summary: summary(sel), monthly: monthly(sel), worst: worstWeeks(sel)}));
