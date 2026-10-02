// TEST ONLY. Loaded before the unchanged production worker in a temporary copy.
// No external requests. Every candidate and purpose below is invented fixture data.
globalThis.__fixtureCalls = [];
globalThis.__fixtureDelay = 0;
globalThis.fetch = async function (url, options = {}) {
  const u = new URL(url);
  if (u.origin !== 'https://api.github.com') throw new Error('Fixture forbids external network');
  globalThis.__fixtureCalls.push(u.pathname + u.search);
  if (globalThis.__fixtureDelay) await new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, globalThis.__fixtureDelay);
    options.signal?.addEventListener('abort', () => {
      clearTimeout(timer); reject(new DOMException('Aborted', 'AbortError'));
    }, {once: true});
  });
  if (options.signal?.aborted) throw new DOMException('Aborted', 'AbortError');
  const items = [
    {full_name:'fixture/clipboard', description:'Fixture clipboard utility', stargazers_count:0, html_url:'https://evil.invalid/stolen'},
    {full_name:'other/rss', description:'Fixture feed reader', stargazers_count:1},
    {full_name:'third/notes', description:'Fixture notes utility', stargazers_count:2}
  ];
  const data = u.pathname === '/search/repositories' ? {items, total_count:3} :
    {full_name:'fixture/start', description:'clipboard utility', topics:['clipboard'], stargazers_count:0};
  return new Response(JSON.stringify(data), {status:200, headers:{'Content-Type':'application/json'}});
};
