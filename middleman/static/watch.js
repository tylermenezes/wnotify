if (!('wnotify' in window)) {
    window.wnotify = {private_key:null};
}

window.wnotify.watcher = new (function(){
    var _this = this;
	var Event = function()
	{
		var _delegates = [];
        /**
         * Registers an event handler
         * @param  callable delegate Event handler to register
         */
        this.register = function(delegate)
        {
            _delegates.push(delegate);
        }

        /**
         * Removes an event handler
         * @param  callable delegate Event handler to remove
         */
        this.deregister = function(delegate)
        {
            for (var i in _delegates) {
                if (_delegates[i] == delegate) {
                    _delegates.splice(i, 1);
                }
            }
        }

        /**
         * Executes all the registered event handlers
         * @params          Paramaters to pass to the event handlers
         */
        this.apply = function()
        {
            for (var i in _delegates) {
                this.callUserFuncArray(_delegates[i], arguments);
            }
        }

        /**
         * Calls a fucntion, passing in an array of values as position-wise arguments
         * e.g. callUserFuncArray(lambda, [1, 2, 3, 'a', 'b', 'c']) calls lambda(1, 2, 3, 'a', 'b', 'c');
         * @param  callable delegate   Function to execute
         * @param  array    parameters Paramaters to pass to the function
         * @return mixed               Result of the function
         */
        this.callUserFuncArray = function (delegate, parameters) {
            var func;

            if (typeof delegate === 'string') {
                func = (typeof this[delegate] === 'function') ? this[delegate] : func = (new Function(null, 'return ' + delegate))();
            }
            else if (Object.prototype.toString.call(delegate) === '[object Array]') {
                func = (typeof delegate[0] == 'string') ? eval(delegate[0] + "['" + delegate[1] + "']") : func = delegate[0][delegate[1]];
            }
            else if (typeof delegate === 'function') {
                func = delegate;
            }

            if (typeof func !== 'function') {
                throw new Error(func + ' is not a valid function');
            }

            return (typeof delegate[0] === 'string') ? func.apply(eval(delegate[0]), parameters) : (typeof delegate[0] !== 'object') ? func.apply(null, parameters) : func.apply(delegate[0], parameters);
        }
	}

    var base = 'http://wnotify.menez.es/'
    var endpoint = null;

    var perEventHandlers = {};
    this.incoming_data = new Event();

	this.event = function(name)
    {
        if (!(name in perEventHandlers)) {
            perEventHandlers[name] = new Event();
        }

        return perEventHandlers[name];
    }

    var handleRawIngomingData = function(data)
    {
        if (data.event in perEventHandlers) {
            perEventHandlers[data.event].apply(data);
        }
    }

    /**
     * Executed when data is recieved, dispatch the event handler and restarts a request
     * @param  {*}      data Data recieved
     */
    var dataRecieved = function(data)
    {
        if (typeof(data) !== 'undefined') {
            _this.incoming_data.apply(data);
        }

        setTimeout(startLongPollThread, 100);
    }

    /**
     * Starts a new long poll thread
     */
    var startLongPollThread = function()
    {
        jQuery.ajax({
            url: endpoint,
            success: dataRecieved,
            error: function(err,e)
            {
                setTimeout(startLongPollThread, 100);
            },
            cache: false,
            dataType: 'json'
        });
    }

    this.beep_on = function(event, sound)
    {
        if (typeof(sound) === 'undefined') {
            sound = 'select';
        }

        this.event(event).register(function(data)
        {
            var sound_obj = jQuery('<audio src="'+ base + 'static/sounds/' + sound + '.mp3" />');
            jQuery("body").append(sound_obj);
            sound_obj.get(0).play();
        })
    }

    this.start = function()
    {
        if (wnotify.private_key == null) {
            throw "Invalid private key!";
        }
        
        endpoint = base + 'watch/' + wnotify.private_key;
        startLongPollThread();
        startLongPollThread();
        startLongPollThread();
    }

	this.constructor = function()
	{
        this.incoming_data.register(handleRawIngomingData);
	}
	this.constructor();
})();