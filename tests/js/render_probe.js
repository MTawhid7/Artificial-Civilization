// Minimal DOM stub: enough to run the viewer's script and assert it produced a
// real wall, without a browser.
//
// The Atlas page is a deliverable that no Python test can see. Everything up to
// the digest is checked in Python; from there on, the only thing standing
// between a typo and a blank page is running the script. This does that: stub
// document, canvas, and getComputedStyle, execute the page's script, then look
// at the pixels it actually wrote.
//
// It asserts on the ImageData rather than on the code, so it fails on the
// symptom a viewer would see — an empty wall, missing markers — rather than on
// how the wall happens to be built today.
//
// Invoked by tests/test_atlas.py, which skips when node is not installed.
const fs = require("fs");
const html = fs.readFileSync(process.argv[2], "utf8");
const js = html.match(/<script>\n([\s\S]*)<\/script>/)[1];

const made = {};
function el(tag) {
  const e = {
    tagName: tag, children: [], style: {}, dataset: {}, classList: {
      add(){}, remove(){}, toggle(){},
    },
    _text: "", _html: "",
    set textContent(v){ this._text = v; }, get textContent(){ return this._text; },
    set innerHTML(v){ this._html = v; }, get innerHTML(){ return this._html; },
    appendChild(c){ this.children.push(c); return c; },
    addEventListener(){}, setAttribute(k,v){ this[k]=v; },
    querySelectorAll(){ return []; },
    getBoundingClientRect(){ return {left:0,top:0,width:1000,height:800}; },
    getContext(){
      return {
        createImageData: (w,h) => ({ width:w, height:h, data:new Uint8ClampedArray(w*h*4) }),
        putImageData: (img) => { e._img = img; },
      };
    },
  };
  return e;
}
const byId = {};
global.document = {
  documentElement: {},
  getElementById(id){ return byId[id] || (byId[id] = el("div")); },
  createElement: el,
  querySelectorAll(){ return []; },
};
global.getComputedStyle = () => ({ getPropertyValue: () => "#171E21" });
global.atob = s => Buffer.from(s, "base64").toString("binary");
global.matchMedia = () => ({ addEventListener(){} });

// `const DIGESTS` inside the eval'd scope is not visible out here; hand it out.
eval(js + "\n;globalThis.__digests = DIGESTS;");

const img = byId["wall"]._img;
if (!img) throw new Error("draw() never painted the wall canvas");
let painted = 0, red = 0;
for (let i = 0; i < img.data.length; i += 4) {
  if (img.data[i+3] === 255) painted++;
  if (img.data[i] > 200 && img.data[i+1] < 130 && img.data[i+2] < 110) red++;
}
console.log(`canvas ${img.width}x${img.height}, ${painted} opaque px, ${red} marker px`);
console.log("provenance:", byId["provenance"].innerHTML.replace(/<[^>]+>/g, " ").trim().slice(0, 110));
console.log("verdict:", JSON.stringify(byId["verdict"].textContent.split("\n")[2]));
console.log("controls:", ["channel","scale","sort"].map(k => byId[k].children.length + " " + k).join(", "));
if (painted < img.width * img.height * 0.2) throw new Error("wall is mostly empty — draw() is not filling bands");
// Only require marker pixels when the digest actually carries markers — a
// fixture with no drawdowns is a valid input, not a rendering failure.
const expected = globalThis.__digests.reduce((n, d) => n + d.markers.length, 0);
if (expected > 0 && red === 0) throw new Error("digest has markers, none drawn");
console.log(`markers: ${expected} in digest, ${red} px drawn`);
console.log("OK");
