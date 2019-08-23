odoo.define('xwh_dms.FileKanbanView', function(require){
'use strict';

var KanbanController = require('web.KanbanController');
var KanbanRenderer = require('web.KanbanRenderer');
var KanbanView = require('web.KanbanView');
var view_registry = require('web.view_registry');

var FileKanbanController = KanbanController.extend({
    renderButtons: function($node){
        this._super.apply(this, arguments)
//        debugger
//        $('<button>Upload</button>').appendTo($node)
    }
});

var FileKanbanRenderer = KanbanRenderer.extend({
    start: function(){
        this._super.apply(this, arguments)
    }
});

var FileKanbanView = KanbanView.extend({
    config: _.extend({}, KanbanView.prototype.config, {
        Controller: FileKanbanController,
        Renderer: FileKanbanRenderer
    }),

    init: function (viewInfo, params) {
        this._super.apply(this, arguments);
    },
});

view_registry.add('file_kanban_view', FileKanbanView);

return FileKanbanView;
})