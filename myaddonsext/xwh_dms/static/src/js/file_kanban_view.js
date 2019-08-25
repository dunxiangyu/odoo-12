odoo.define('xwh_dms.FileKanbanView', function(require){
'use strict';

var KanbanController = require('web.KanbanController');
var KanbanRenderer = require('web.KanbanRenderer');
var KanbanView = require('web.KanbanView');
var view_registry = require('web.view_registry');
var DocumentViewer = require('xwh_dms.DocumentViewer');

var FileKanbanController = KanbanController.extend({
});

var FileKanbanRenderer = KanbanRenderer.extend({
    events: _.extend({}, KanbanRenderer.prototype.events, {
        'click .oe_kanban_file_preview': '_onFilePreview'
    }),
    _onFilePreview: function(event){
        var id = event.currentTarget.getAttribute('data-id')
        var datas = this.state.data.map(function(item){return {
            id: item.data.id,
            name: item.data.name,
            filename: item.data.datas_fname,
            url: item.data.url,
            mimetype: item.data.mimetype,
        }});
        var viewer = new DocumentViewer(this, datas, parseInt(id))
        viewer.appendTo($('body'))
    },
});

var FileKanbanView = KanbanView.extend({
    config: _.extend({}, KanbanView.prototype.config, {
        Controller: FileKanbanController,
        Renderer: FileKanbanRenderer
    }),
});

view_registry.add('file_kanban_view', FileKanbanView);

return FileKanbanView;
})