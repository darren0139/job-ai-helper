const fs=require('node:fs'),path=require('node:path');
const {chromium}=require('../../.venv/Lib/site-packages/playwright/driver/package');
const out=__dirname,shots=path.join(out,'screenshots');fs.mkdirSync(shots,{recursive:true});
const r={url:'http://127.0.0.1:8701/',entrypoint:path.resolve(out,'../../app.py'),cwd:path.join(out,'disposable'),screenshots:[],page_errors:[],console_errors:[]};
(async()=>{const b=await chromium.launch({headless:true,chromiumSandbox:true,executablePath:'C:/Users/Admin/AppData/Local/ms-playwright/chromium-1254/chrome-win64/chrome.exe'});const p=await b.newPage({viewport:{width:1440,height:1100},acceptDownloads:true});
p.on('pageerror',e=>r.page_errors.push(String(e)));p.on('console',m=>{if(m.type()==='error')r.console_errors.push(m.text())});
await p.route('**/*',route=>['127.0.0.1','localhost'].includes(new URL(route.request().url()).hostname)?route.continue():route.abort());
async function settle(){await p.waitForTimeout(350);await p.getByRole('button',{name:'Stop',exact:true}).waitFor({state:'hidden',timeout:120000});await p.waitForTimeout(500)}
async function tab(name){await p.getByRole('tab',{name,exact:true}).click();await settle()}
async function select(label,value){const box=p.getByTestId('stSelectbox').filter({has:p.getByText(label,{exact:true})}).last();await box.getByRole('combobox').click();await p.getByRole('option',{name:value,exact:true}).click();await settle()}
async function shot(file,loc){await settle();await loc.scrollIntoViewIfNeeded();await p.screenshot({path:path.join(shots,file)});r.screenshots.push({file,viewport:p.viewportSize()});console.log(file)}
try{
 await p.goto(r.url);await p.getByText('Bullet-Choice Benchmark Lab',{exact:true}).first().waitFor({timeout:120000});await p.getByText('Bullet-Choice Benchmark Lab',{exact:true}).first().click();await settle();
 await shot('01-navigation.png',p.getByRole('heading',{name:'Bullet-Choice Benchmark Lab',exact:true}));
 await tab('Run Benchmarks');await p.getByRole('button',{name:'Run All Benchmarks',exact:true}).click();await settle();
 await tab('Benchmark Overview');await shot('02-overview.png',p.getByRole('heading',{name:'Benchmark Overview',exact:true}));
 await tab('JD & Bullet Comparison Explorer');await shot('03-synthetic.png',p.getByRole('heading',{name:'JD & Bullet Comparison Explorer',exact:true}));
 await select('Explorer dataset','corpus');await shot('04-corpus.png',p.getByRole('heading',{name:'JD & Bullet Comparison Explorer',exact:true}));
 await select('Explorer dataset','real');await select('Case','R07');await shot('05-real.png',p.getByRole('heading',{name:'JD & Bullet Comparison Explorer',exact:true}));
 await tab('Best-of Optimizer Evaluation');await shot('06-selector.png',p.getByRole('heading',{name:'Best-of Optimizer Evaluation',exact:true}));
 await tab('Previous vs Current');await shot('07-before-after.png',p.getByRole('heading',{name:'Previous vs Current',exact:true}));
 await tab('Exports and Optional Review');for(const [name,file] of [['Download benchmark JSON','ui-run.json'],['Download results CSV','ui-results.csv'],['Download benchmark ZIP','ui-benchmark.zip']]){const pending=p.waitForEvent('download');await p.getByRole('button',{name,exact:true}).click();await(await pending).saveAs(path.join(out,file))}
 r.lab_exceptions=await p.getByTestId('stException').allTextContents();
 await p.setViewportSize({width:760,height:1100});await tab('JD & Bullet Comparison Explorer');await shot('08-narrow.png',p.getByRole('heading',{name:'JD & Bullet Comparison Explorer',exact:true}));r.overflow=await p.evaluate(()=>{const m=document.querySelector('[data-testid=stMain]');return {client:m.clientWidth,scroll:m.scrollWidth}});
 await p.setViewportSize({width:1440,height:1100});await p.getByText('Application Sessions',{exact:true}).first().click();await settle();await p.locator('.st-key-load_app_2 button').click();await settle();await p.getByText('Open Best-of résumé comparison',{exact:true}).waitFor({timeout:120000});await p.getByText('Open Best-of résumé comparison',{exact:true}).click();await settle();
 await p.getByRole('heading',{name:'JD Relevance Comparison',exact:true}).first().waitFor({timeout:120000});await shot('09-normal-tailor.png',p.getByRole('heading',{name:'JD Relevance Comparison',exact:true}).first());r.final_exceptions=await p.getByTestId('stException').allTextContents();
}catch(e){r.error=String(e);r.body=(await p.locator('body').innerText()).slice(-14000);await p.screenshot({path:path.join(shots,'failure.png')})}finally{await b.close();fs.writeFileSync(path.join(out,'browser.json'),JSON.stringify(r,null,2))}})().catch(e=>{r.error=String(e);fs.writeFileSync(path.join(out,'browser.json'),JSON.stringify(r,null,2));console.error(e)});
