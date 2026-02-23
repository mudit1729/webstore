/* Minimal JS for catalog interactions */

// Lazy loading for images (progressive enhancement)
document.addEventListener('DOMContentLoaded', function () {
    // Image loading indicator
    document.querySelectorAll('.product-image img').forEach(function (img) {
        img.addEventListener('load', function () {
            this.style.opacity = '1';
        });
        if (img.complete) {
            img.style.opacity = '1';
        }
    });
});
