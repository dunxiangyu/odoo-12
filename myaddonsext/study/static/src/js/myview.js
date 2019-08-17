odoo.define('study.myview', function(require){
"use strict";

var AbstractController = require('web.AbstractController');
var AbstractModel = require('web.AbstractModel')
var AbstractRenderer = require('web.AbstractRenderer')
var AbstractView = require('web.AbstractView')
var viewRegistry = require('web.view_registry')

var MyViewController = AbstractController.extend({});
var MyViewRenderer = AbstractRenderer.extend({
    className: "o_myview",

    on_attach_callback: function(){
        this.isInDom = true;
        this._renderMap()
    },

    _render: function(){
        if (this.isInDom){
            this._renderMap();
            return $.when();
        }

        this.$el.append(
            $('<h1>').text('Hello, My View!'),
            $('<div style="width: 100%; height: 400px; position: relative; outline: none;" id="mapid" class="leaflet-container leaflet-touch leaflet-retina leaflet-fade-anim leaflet-grab leaflet-touch-drag leaflet-touch-zoom" />')
        );
        return $.when()
    },

    _renderMap: function(){
        if (!this.mymap){
            this.mymap = L.map('mapid').setView([51.505, -0.09], 13);
            this.mymap.on('click', function(e){
                alert(e.latlng)
//                var popup = L.popup();
//                popup.setLatLng(e.latlng).setContent('你点击的位置在' + e.latlng.toString())
//                .openOn(this.mymap);
            });

            L.tileLayer('https://api.tiles.mapbox.com/v4/{id}/{z}/{x}/{y}.png?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpejY4NXVycTA2emYycXBndHRqcmZ3N3gifQ.rJcFIG214AriISLbB6B5aw', {
                maxZoom: 18,
                attribution: 'Map data &copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors, ' +
                    '<a href="https://creativecommons.org/licenses/by-sa/2.0/">CC-BY-SA</a>, ' +
                    'Imagery © <a href="https://www.mapbox.com/">Mapbox</a>',
                id: 'mapbox.streets'
            }).addTo(this.mymap);
        }
        this._renderMarker();
    },

    _renderMarker: function(){
        self = this
        self.markers = []
        this.state.contacts.forEach(function(contact){
            L.marker([51.5, -0.09], {title: contact.name, contact_id: contact.id})
            .addTo(self.mymap)
            .on('click', self._onContactMarkerClick.bind(self));

            if (contact.partner_latitude && contact.partner_longitude){
                self.markers.push(
                    L.marker(
                        [contact.partner_latitude, contact.partner_longitude],
                        {title: contact.name, contact_id: contact.id}
                    )
                    .addTo(self.mymap)
                    .on('click', self._onContactMarkerClick.bind(self))
                );
            }
        });
    },

    _onContactMarkerClick: function(event){
        var action = {
            type: 'ir.actions.act_window',
            views: [[false, 'form']],
            res_model: 'res.company',
            res_id: event.target.options.contact_id,
        }
        this.do_action(action);
    }
});
var MyViewModel = AbstractModel.extend({
    get: function(){
        return {contacts: this.contacts}
    },

    load: function(params){
        this.displayContacts = params.displayContacts == 0 ? false : true;
        return this._load(params)
    },

    reload: function(id, params){
        return this._load(params)
    },

    _load: function(params){
        this.domain = params.domain || this.domain || [];
        if (this.displayContacts){
            var self = this;
            return this._rpc({
                model: 'res.company',
                method: 'search_read',
                fields: ['id', 'name', 'partner_latitude', 'partner_longitude'],
                domain: this.domain,
            })
            .then(function(result){
                self.contacts = result;
            })
        }
        this.contacts = [];
        return $.when();
    }
})

var MyView = AbstractView.extend({
    config: {
        Model: MyViewModel,
        Controller: MyViewController,
        Renderer: MyViewRenderer,
    },
    viewType: 'myview',
    cssLibs: [
        '/study/static/lib/leaflet/leaflet.css',
    ],
    jsLibs: [
        '/study/static/lib/leaflet/leaflet.js',
    ],
    init: function(){
        this._super.apply(this, arguments);
        this.loadParams.displayContacts = this.arch.attrs.display_contacts;
    },
});

viewRegistry.add('myview', MyView);

return MyView;

})