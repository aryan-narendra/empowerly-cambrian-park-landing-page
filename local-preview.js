/* Adapt only resource access and outbound links for a local preview. */
(() => {
  const staticSite = window.__EMPOWERLY_STATIC__;
  const reply = value => Promise.resolve(new Response(JSON.stringify(value), {headers:{'Content-Type':'application/json'}}));
  const canonicalVariables = variables => JSON.stringify(Object.fromEntries(Object.entries(variables || {}).filter(([key])=> !['startAfter','publishedBefore'].includes(key)).sort(([a],[b])=>a.localeCompare(b))));
  function staticImages(value) {
    if (Array.isArray(value)) return value.map(staticImages);
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key,item])=>[key,staticImages(item)]));
    if (typeof value === 'string' && value.startsWith('/assets/cdn/')) return location.origin + staticSite.basePath + encodeURI(value);
    return value;
  }
  const originalFetch = window.fetch.bind(window);
  window.fetch = (input, options) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    if (url.startsWith('https://connect-api.empowerly.com/graphql')) {
      // Give the embedded form a local session so its initialization effect does
      // not retry continuously. No production form or lead is created.
      const payload = typeof options?.body === 'string' ? JSON.parse(options.body) : null;
      if (payload?.operationName === 'InitializeFlow') {
        return Promise.resolve(new Response(JSON.stringify({data:{initializeFlow:{success:true,executionId:'local-preview',message:null}}}), {headers:{'Content-Type':'application/json'}}));
      }
      if (payload?.operationName === 'GetCurrentNode' && payload.variables?.executionId === 'local-preview') {
        return Promise.resolve(new Response(JSON.stringify({data:{getCurrentNode:{success:true,currentNode:null,progressInfo:null,availableActions:[],validationFeedbacks:[],message:null}}}), {headers:{'Content-Type':'application/json'}}));
      }
      if (staticSite) {
        if (/\bmutation\b/.test(payload?.query || '')) {
          const field = payload.query.match(/\{\s*(\w+)/)?.[1] || 'localPreview';
          return reply({data:{[field]:{success:true,message:null,id:'static-preview',data:null}}});
        }
        const record = staticSite.records.find(item => item.operationName === payload?.operationName && canonicalVariables(item.variables) === canonicalVariables(payload?.variables));
        return reply(record ? staticImages(record.response) : {data:null,errors:[{message:'This static design preview has no captured response for this query.'}]});
      }
      return originalFetch('/preview-api/graphql', options);
    }
    return originalFetch(input, options);
  };
  // Keep both local drafts available; other site pages stay on Empowerly.
  document.addEventListener('click', event => {
    const carouselButton = event.target.closest?.('[data-carousel-step]');
    if (carouselButton) {
      const carousel = carouselButton.closest('.local-school-carousel');
      moveSchools(carousel, Number(carouselButton.dataset.carouselStep));
      return;
    }
    const anchor = event.target.closest?.('a[href]');
    if (!anchor) return;
    const target = new URL(anchor.getAttribute('href'), location.href);
    if (target.origin !== location.origin) return;
    if (target.pathname.replace(/\/$/, '') === location.pathname.replace(/\/$/, '') && target.hash) return;
    if (anchor.getAttribute('href').startsWith('#')) return;
    const sitePath = staticSite && target.pathname.startsWith(staticSite.basePath + '/') ? target.pathname.slice(staticSite.basePath.length) : target.pathname;
    if (['/locations/palo-alto', '/locations/cambrian-park'].includes(sitePath.replace(/\/$/, ''))) {
      event.preventDefault();
      event.stopImmediatePropagation();
      location.assign(staticSite ? staticSite.basePath + sitePath.replace(/\/$/, '') + '/' + target.search + target.hash : target.href);
      return;
    }
    event.preventDefault();
    event.stopImmediatePropagation();
    window.open('https://empowerly.com' + sitePath + target.search + target.hash, anchor.target || '_self');
  }, true);

  function moveSchools(carousel, direction) {
    const track = carousel.querySelector('.local-school-track');
    const card = track.querySelector('.local-school-card');
    const gap = parseFloat(getComputedStyle(track).gap) || 0;
    const visible = matchMedia('(max-width: 600px)').matches ? 1 : 2;
    track.scrollBy({left: direction * (card.offsetWidth + gap) * visible, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'});
  }
  document.addEventListener('keydown', event => {
    if (!event.target.matches?.('.local-school-track') || !['ArrowLeft','ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    moveSchools(event.target.closest('.local-school-carousel'), event.key === 'ArrowRight' ? 1 : -1);
  });
  const boundTracks = new WeakSet();
  function bindCarousels() {
    document.querySelectorAll('.local-school-track').forEach(track => {
      if (boundTracks.has(track)) return;
      boundTracks.add(track);
      track.addEventListener('scroll', () => {
        const carousel = track.closest('.local-school-carousel');
        carousel.querySelector('[data-carousel-step="-1"]').disabled = track.scrollLeft < 2;
        carousel.querySelector('[data-carousel-step="1"]').disabled = track.scrollLeft + track.clientWidth >= track.scrollWidth - 2;
      }, {passive:true});
    });
  }
  document.addEventListener('DOMContentLoaded', bindCarousels);
  new MutationObserver(bindCarousels).observe(document.documentElement, {childList:true,subtree:true});
})();
