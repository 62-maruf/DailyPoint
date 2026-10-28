async function api(url, data) {
  const opt = data === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) };
  const r = await fetch(url, opt);
  return r.json();
}
const $ = (id) => document.getElementById(id);
