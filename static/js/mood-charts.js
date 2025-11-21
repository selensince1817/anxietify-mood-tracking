(function () {
  function baseConfig(labels, values) {
    return {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'valence',
            data: values,
            backgroundColor: 'rgba(30, 215, 96, 0.2)',
            borderColor: 'rgb(30, 215, 96)',
            borderWidth: 3,
            tension: 0.2,
            pointRadius: 3,
            pointBorderColor: 'rgba(0, 0, 0, 0)',
            pointBackgroundColor: 'rgba(0, 0, 0, 0)'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        elements: {
          point: {
            radius: 3
          }
        },
        scales: {
          y: {
            grid: {
              display: false,
              drawBorder: false
            }
          },
          x: {
            grid: {
              display: false,
              drawBorder: false
            }
          }
        }
      }
    };
  }

  window.renderMoodChart = function ({ canvasId, labels, values }) {
    var canvas = document.getElementById(canvasId);
    if (!canvas || typeof Chart === 'undefined') {
      return;
    }

    var ctx = canvas.getContext('2d');
    var config = baseConfig(labels, values);
    new Chart(ctx, config);
  };
})();
