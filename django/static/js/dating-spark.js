/* Знакомства: soft stage motion + match banner presence */
(function () {
  var stage = document.getElementById("dating-stage");
  if (stage) {
    stage.classList.add("is-in");
  }
  var banner = document.getElementById("dating-match-banner");
  if (banner) {
    banner.classList.add("is-pop");
    try {
      if (!window.AudioContext && !window.webkitAudioContext) return;
      var ctx = new (window.AudioContext || window.webkitAudioContext)();
      var o = ctx.createOscillator();
      var g = ctx.createGain();
      o.type = "sine";
      o.frequency.value = 660;
      o.connect(g);
      g.connect(ctx.destination);
      var now = ctx.currentTime;
      g.gain.setValueAtTime(0.0001, now);
      g.gain.exponentialRampToValueAtTime(0.05, now + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, now + 0.22);
      o.start(now);
      o.stop(now + 0.25);
    } catch (e) {}
  }
})();
