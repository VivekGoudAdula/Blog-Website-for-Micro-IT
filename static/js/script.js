// Custom JavaScript can go here

document.addEventListener('DOMContentLoaded', function() {
    // Example: Make alerts dismissible after a timeout
    setTimeout(function() {
        let alerts = document.querySelectorAll('.alert-dismissible');
        alerts.forEach(function(alert) {
            if (alert) {
                // Use Bootstrap's alert close method if available
                // Otherwise, just hide it.
                var alertInstance = bootstrap.Alert.getInstance(alert);
                if (alertInstance) {
                    alertInstance.close();
                } else {
                    alert.style.display = 'none';
                }
            }
        });
    }, 5000); // Hide after 5 seconds

    // Handle Bootstrap tabs activation from URL hash for admin panel
    var hash = window.location.hash;
    if (hash) {
        var triggerEl = document.querySelector('#adminTab a[href="' + hash + '"]');
        if (triggerEl) {
            var tab = new bootstrap.Tab(triggerEl);
            tab.show();
        }
    }

    // Update URL hash when a tab is shown
    var tabElms = document.querySelectorAll('#adminTab a[data-toggle="tab"]');
    tabElms.forEach(function(tabElm) {
        tabElm.addEventListener('shown.bs.tab', function (event) {
            history.pushState(null, null, event.target.hash);
        });
    });

}); 