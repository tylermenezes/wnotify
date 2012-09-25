(function(){
var wnotify_watcher = new (function(){
    var _this = this;
    var base = 'http://wnotify.menez.es/track/'
    
    this.public_key = null;
    this.private_key = null;

    this.track = function(event, data)
    {
        if (typeof(data) === 'undefined') {
            data = {};
        }

        if (this.public_key == null) {
            throw "Invalid public key!";
        }

        jQuery.ajax({
            url: base + _this.public_key + '/' + event,
            data: data,
            cache: false,
            dataType: 'json'
        });
    }
})();

if ('wnotify' in window) {
    wnotify_watcher.watcher = window.wnotify.watcher;
    wnotify_watcher.private_key = window.wnotify.private_key;
}

window.wnotify = wnotify_watcher;
})();