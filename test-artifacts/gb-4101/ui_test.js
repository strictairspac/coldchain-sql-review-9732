const {chromium}=require('playwright-core');
const OUT='/workspace/test-artifacts/gb-4101/';
let failures=0;
const check=(name,cond,extra='')=>{console.log(cond?'PASS':'FAIL',name,cond?'':extra);if(!cond)failures++};
(async()=>{
  const b=await chromium.launch({args:['--no-sandbox']});
  const page=await b.newPage();
  page.setDefaultTimeout(15000);
  // 登录（表单预填 operator 演示账号）
  await page.goto('http://127.0.0.1:8080/');
  await page.click('#login button[type=submit]');
  await page.waitForSelector('text=样本库');
  check('登录进入工作台',true);
  // 打开调号页
  await page.goto('http://127.0.0.1:8080/#renumber');
  await page.waitForSelector('#rn-form');
  const nav=await page.textContent('nav');
  check('导航含 05 账单调号',nav.includes('账单调号'),nav);
  // 互换示例 → 整批生效
  await page.click('#ex-swap');
  await page.click('#rn-form button.primary');
  await page.waitForSelector('#result .badge.applied');
  let txt=await page.textContent('#result');
  check('页面办理互换：显示整批生效',txt.includes('整批生效'),txt.slice(0,200));
  check('页面办理互换：明细两行均生效',(await page.$$eval('#result .badge.applied',els=>els.length))>=2);
  await page.screenshot({path:OUT+'ui-swap-applied.png',fullPage:true});
  // 冲突示例 → 整批退回并标出冲突号
  await page.fill('[name=moves]','105,106\n108,969');
  await page.click('#rn-form button.primary');
  await page.waitForSelector('#result .badge.rejected');
  txt=await page.textContent('#result');
  check('页面办理冲突：显示整批退回',txt.includes('整批退回'),txt.slice(0,200));
  check('页面办理冲突：标出冲突号码 106',txt.includes('冲突')&&txt.includes('106'),txt.slice(0,300));
  check('页面办理冲突：另一行随批退回',txt.includes('随批退回'),txt.slice(0,300));
  await page.screenshot({path:OUT+'ui-conflict-rejected.png',fullPage:true});
  // 历史记录可查明细（原结论可查）
  await page.click('#refresh');
  await page.waitForSelector('a[href^="#renumber/"]');
  const links=await page.$$('a[href^="#renumber/"]');
  check('历史列表含可调明细的批次',links.length>0);
  await page.click('a[href^="#renumber/"] >> nth=0');
  await page.waitForSelector('#result .panel');
  check('点击历史批次展示明细结论',(await page.textContent('#result')).includes('幂等键'));
  // 恢复互换（把 101/202 换回去）
  await page.goto('http://127.0.0.1:8080/#renumber');
  await page.waitForSelector('#rn-form');
  await page.click('#ex-swap');
  await page.click('#rn-form button.primary');
  await page.waitForSelector('#result .badge.applied');
  check('恢复互换再次生效',true);
  // viewer 只读
  await page.click('#logout');
  await page.waitForSelector('#login');
  await page.fill('[name=email]','viewer@chenggang.test');
  await page.click('#login button[type=submit]');
  await page.waitForSelector('text=样本库');
  await page.goto('http://127.0.0.1:8080/#renumber');
  await page.waitForSelector('#rn-form');
  check('viewer 页面提交按钮禁用',await page.isDisabled('#rn-form button.primary'));
  await page.screenshot({path:OUT+'ui-viewer-readonly.png',fullPage:true});
  await b.close();
  console.log(failures?`\n==== UI 测试 ${failures} 项失败 ====`:'\n==== UI 测试全部通过 ====');
  process.exit(failures?1:0);
})().catch(e=>{console.error('ERROR',e.message);process.exit(1)});
