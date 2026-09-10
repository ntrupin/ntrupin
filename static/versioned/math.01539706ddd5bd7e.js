window.MathJax = {
  loader: {
    load: ['ui/safe']
  },
  output: {
    fontPath: 'https://cdn.jsdelivr.net/npm/@mathjax/%%FONT%%-font@4.1.3'
  },
  options: {
    enableMenu: false,
    safeOptions: {
      allow: { URLs: 'safe', classes: 'none', cssIDs: 'none', styles: 'none' }
    }
  },
  tex: {
    inlineMath: {'[+]': [['$', '$']]}
  }
};
