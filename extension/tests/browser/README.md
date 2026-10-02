# Chromium acceptance (fixture network)

```sh
cd extension/tests/browser
npm ci
npx playwright install --with-deps chromium
xvfb-run -a npm test
```

CI executes actual Chromium MV3 worker, isolated content scripts, options UI,
Chrome storage access restrictions and two independent profiles. No API key is
required and no model/GitHub HTTP requests are sent. GitHub DOM and HTTP replies
are explicitly invented fixtures. Production JS is copied unchanged and its
hashes are recorded. Only the temporary test manifest worker entry and an extra
storage probe differ; neither is included in the release ZIP.

browser-results.json records passed steps; CI uploads it even on failure.
A pass is browser engineering evidence, not live search quality, model provider
compatibility, outside-user installation or a human usability session.
