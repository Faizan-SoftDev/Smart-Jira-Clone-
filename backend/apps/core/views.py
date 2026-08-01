"""Public legal pages served independently from authenticated product APIs."""

from django.shortcuts import render
from django.http import HttpResponse


def privacy_policy(request):
    return render(request, "legal/privacy.html")


def terms_of_service(request):
    return render(request, "legal/terms.html")


def refund_policy(request):
    return render(request, "legal/refunds.html")


def robots_txt(request):
    return HttpResponse("User-agent: *\nAllow: /privacy/\nAllow: /terms/\nAllow: /refunds/\nDisallow: /api/\nDisallow: /ws/\n", content_type="text/plain")


def sitemap_xml(request):
    content = """<?xml version=\"1.0\" encoding=\"UTF-8\"?><urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\"><url><loc>/privacy/</loc></url><url><loc>/terms/</loc></url><url><loc>/refunds/</loc></url></urlset>"""
    return HttpResponse(content, content_type="application/xml")
