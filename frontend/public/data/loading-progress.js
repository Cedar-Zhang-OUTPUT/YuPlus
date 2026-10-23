// Simulated activity only: no byte counts or fabricated completion percentage.
export function loadingProgress() {
  const section = document.createElement('section');
  section.className = 'loading-progress';
  section.setAttribute('aria-label', '正在读取项目内容');
  const title = document.createElement('h3');title.textContent = '正在读取项目内容';
  const track = document.createElement('div');track.className = 'loading-progress-track';
  track.setAttribute('role', 'progressbar');track.setAttribute('aria-label', '正在读取项目内容');
  track.setAttribute('aria-valuetext', '正在读取'); // Indeterminate, not actual measured progress.
  const fill = document.createElement('div');fill.className = 'loading-progress-fill';
  track.append(fill);
  const note = document.createElement('p');note.className = 'small muted';note.textContent = '即将呈现项目内容';
  section.append(title,track,note);
  const started = Date.now();
  fill.style.transform = 'scaleX(0.04)';
  const timer = setInterval(() => {
    const elapsed = Math.max(0, Date.now()-started);
    fill.style.transform = `scaleX(${Math.min(.92,.04+.88*(1-Math.exp(-elapsed/4200)))})`;
  },200);
  let completion,resolveCompletion;
  function stop() {
    clearInterval(timer);clearTimeout(completion);
    resolveCompletion?.();resolveCompletion=null;
  }
  function finish() {
    stop();
    fill.style.transitionDuration = '160ms';fill.style.transform = 'scaleX(1)';
    track.setAttribute('aria-valuetext','读取完成');
    // Fast reads should not be slowed down merely to show an animation.
    if (Date.now()-started<200) return Promise.resolve();
    return new Promise(resolve => {resolveCompletion=resolve;completion=setTimeout(() => {resolveCompletion=null;resolve();},170);});
  }
  return {element:section,finish,stop};
}
