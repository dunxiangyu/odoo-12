odoo.define('xwh_dms.DocumentViewer', function(require){

var DocumentViewer = require('mail.DocumentViewer');

var Viewer = DocumentViewer.extend({
    init: function (parent, attachments, activeAttachmentID){
        this._super.apply(this, arguments)
    },

    start: function () {
        debugger
//        <iframe class="mt32 o_viewer_text" t-if="(widget.activeAttachment.type || '').indexOf('text') !== -1"
//  t-attf-src="/web/content/#{widget.activeAttachment.id}" />
        $('<div>hello</div>').appendTo($('.o_viewer_zoomer', this.$el))
        this._super.apply(this, arguments)
    },
})

return Viewer
});