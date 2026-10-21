import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

// Exercise the production renderer without booting the whole application.
const app = await readFile(new URL('../public/app.js', import.meta.url), 'utf8');
const renderer = app.slice(app.indexOf('function sourceLink('), app.indexOf('function sourceLinksOf('));
function render(source, version) {
  const inspections = [];
  const context = vm.createContext({
    DATA: {PROVIDERS: {local: {label: '本地文件', hue: 'gray'}}, meta: {demo: false}},
    svOf: id => id === version.id ? version : null, srcOfSv: () => source,
    hueOf: x => x, openInspector: spec => inspections.push(spec),
    el: (tag, className) => ({tag, className, children: [], style: {setProperty() {}},
      classList: {add() {}}, append(...nodes) { this.children.push(...nodes); }}),
  });
  vm.runInContext(renderer, context);
  const node = context.sourceLink(version.id);
  return {title: node.children[1], reference: node.children[2], inspections};
}
const original = {role: 'original', availability: 'available', url: '/api/assets?project=p&version=old&asset=pdf'};
const source = {id: 'src', provider: 'local', cached_title: '项目 Brief.pdf', latest_snapshot_id: 'new'};
const version = assets => ({id: 'old', source_id: 'src', assets});

test('local title opens the cited original PDF, while provenance remains a separate action', () => {
  const {title, reference, inspections} = render(source, version([
    {role: 'body', availability: 'available', url: '/extracted.txt'}, original,
  ]));
  assert.equal(title.href, '/api/assets?project=p&version=old&asset=pdf');
  assert.equal(title.target, '_blank');
  assert.equal(title.rel, 'noopener noreferrer');
  assert.equal(title.onclick, undefined);
  reference.onclick();
  assert.equal(inspections[0].id, 'src');
  assert.equal(inspections[0].sv, 'old');
});

test('one saved file without an original role can still be opened', () => {
  const {title} = render(source, version([{...original, role: 'body'}]));
  assert.equal(title.href, original.url);
});

test('missing or changed originals and ambiguous multi-file sources expose their exact snapshot instead', () => {
  for (const assets of [[], [{...original, availability: 'missing'}],
    [{...original, availability: 'changed'}, {role: 'preview', availability: 'available', url: '/preview.png'}],
    [original, {...original, url: '/second.pdf'}]]) {
    const {title, inspections} = render(source, version(assets));
    assert.equal(title.href, '#');
    let prevented = false;
    title.onclick({preventDefault() {prevented = true;}});
    assert.ok(prevented);
    assert.equal(inspections[0].sv, 'old');
  }
});

test('Feishu titles keep opening their canonical document, even with saved attachments', () => {
  const {title} = render({...source, provider: 'feishu', canonical_url: 'https://example.feishu.cn/docx/abc'}, version([original]));
  assert.equal(title.href, 'https://example.feishu.cn/docx/abc');
  assert.equal(title.target, '_blank');
});
