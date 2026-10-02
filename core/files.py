"""Serving uploaded files (PDFs) inline or as downloads, for local or cloud storage."""
import os

from django.core.files.storage import FileSystemStorage
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.utils.text import slugify


def serve_file(field_file, title, as_attachment=False):
    if not field_file:
        raise Http404("File not available")
    if not isinstance(field_file.storage, FileSystemStorage):
        # Cloud storage: redirect to a (signed) URL instead of proxying bytes.
        return HttpResponseRedirect(field_file.url)
    try:
        handle = field_file.open("rb")
    except (FileNotFoundError, OSError):
        raise Http404("File not available")
    extension = os.path.splitext(field_file.name)[1] or ".pdf"
    response = FileResponse(handle, as_attachment=as_attachment,
                            filename=f"{slugify(title) or 'document'}{extension}",
                            content_type="application/pdf")
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, max-age=3600"
    return response
