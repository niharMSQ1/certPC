import re
import json
import difflib
from io import BytesIO
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from django.shortcuts import render, get_object_or_404
from pdfminer.high_level import extract_text
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from .models import Framework, Policy, PolicyVersion, PolicySection, PolicyDiff
from django.db.models import Q

@require_GET
def get_frameworks(request):
    frameworks = Framework.objects.all().values('id', 'name')
    return JsonResponse(list(frameworks), safe=False)

@csrf_exempt
def create_framework(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name')
            description = data.get('description', '')
            if not name:
                return JsonResponse({'error': 'Name is required'}, status=400)
            framework = Framework.objects.create(name=name, description=description)
            return JsonResponse({'message': 'Framework created', 'framework_id': framework.id}, status=201)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    return JsonResponse({'error': 'Only POST allowed'}, status=405)

@csrf_exempt
def upload_policy_pdf(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)

    try:
        framework_id = int(request.POST['framework_id'])
        title = request.POST['policy_title']
        version = request.POST['version']
        uploaded_file = request.FILES.get('uploaded_file')
        text_content = request.POST.get('text_content')
    except (KeyError, ValueError) as e:
        return JsonResponse({'error': f'Missing or invalid input: {str(e)}'}, status=400)

    if not text_content and not uploaded_file:
        return JsonResponse({'error': 'Either text content or a PDF file must be provided'}, status=400)

    if text_content:
        lines = text_content.strip().splitlines()
    elif uploaded_file:
        buffer = BytesIO(uploaded_file.read())
        text = extract_text(buffer)
        lines = text.strip().splitlines()
    else:
        return JsonResponse({'error': 'No content provided'}, status=400)

    if len(lines) < 1:
        return JsonResponse({'error': 'Content must have at least a title'}, status=400)

    content_lines = lines

    section_pattern = re.compile(r'^(\d+(\.\d+)*)$')
    sections = {}
    current_section = None
    content_buffer = []

    for line in content_lines:
        line = line.strip()
        if section_pattern.match(line):
            if current_section and content_buffer:
                sections[current_section] = '\n'.join(content_buffer).strip()
                content_buffer = []
            current_section = line
        elif current_section and line:
            content_buffer.append(line)

    if current_section and content_buffer:
        sections[current_section] = '\n'.join(content_buffer).strip()

    try:
        framework = Framework.objects.get(id=framework_id)
    except Framework.DoesNotExist:
        return JsonResponse({'error': 'Framework not found'}, status=404)

    policy, _ = Policy.objects.get_or_create(framework=framework, title=title)
    version_obj, created = PolicyVersion.objects.get_or_create(
        policy=policy,
        version=version,
        defaults={'uploaded_file': uploaded_file}
    )

    if not created and uploaded_file:
        version_obj.uploaded_file = uploaded_file
        version_obj.save()

    existing_sections = PolicySection.objects.filter(version=version_obj)
    existing_section_map = {s.section_number: s for s in existing_sections}
    
    existing_sections.exclude(Q(section_number__in=sections.keys())).update(archived=True)

    prev_versions = PolicyVersion.objects.filter(policy=policy).exclude(id=version_obj.id).order_by('-created_at')
    old_sections = {}
    if prev_versions.exists():
        prev = prev_versions.first()
        old_sections = {s.section_number: s.content for s in prev.sections.all()}

    changes = []
    deprecations = []
    
    for sec_num, content in sections.items():
        old_content = old_sections.get(sec_num, "")
        section = existing_section_map.get(sec_num)
        
        if section:
            if section.content.strip() == content.strip():
                section.archived = False
                section.save()
                continue
            
            section.content = content
            section.archived = False
            section.save()
        else:
            section = PolicySection.objects.create(
                version=version_obj,
                section_number=sec_num,
                content=content,
                archived=False
            )

        if not section or old_content.strip() != content.strip():
            diff = '\n'.join(difflib.unified_diff(
                old_content.splitlines(),
                content.splitlines(),
                fromfile=f'{prev.version}:{sec_num}' if prev_versions.exists() else 'original',
                tofile=f'{version}:{sec_num}',
                lineterm=''
            ))
            
            change_type = "modified" if sec_num in old_sections else "added"
            
            changes.append({
                'section': sec_num,
                'type': change_type,
                'old_content': old_content,
                'new_content': content,
                'diff': diff
            })
            
            PolicyDiff.objects.create(
                version=version_obj,
                section_number=sec_num,
                diff_text=diff,
                change_details={
                    'change_type': change_type,
                    'old_content': old_content,
                    'new_content': content,
                    'timestamp': version_obj.created_at.isoformat(),
                    'diff': diff
                }
            )

    for sec_num in set(old_sections.keys()) - set(sections.keys()):
        deprecations.append({
            'section': sec_num,
            'content': old_sections[sec_num],
            'removed_in_version': version
        })
        
        PolicyDiff.objects.create(
            version=version_obj,
            section_number=sec_num,
            diff_text=f"Section {sec_num} was removed",
            change_details={
                'change_type': 'removed',
                'old_content': old_sections[sec_num],
                'new_content': '',
                'timestamp': version_obj.created_at.isoformat(),
                'diff': f"Section {sec_num} was removed in version {version}"
            }
        )

    change_summary = {
        'version': version,
        'policy_title': title,
        'framework': framework.name,
        'created_at': version_obj.created_at.isoformat(),
        'changes': changes,
        'deprecations': deprecations,
        'stats': {
            'sections_added': len([c for c in changes if c['type'] == 'added']),
            'sections_modified': len([c for c in changes if c['type'] == 'modified']),
            'sections_removed': len(deprecations),
            'total_sections': len(sections)
        }
    }
    
    version_obj.change_summary = change_summary
    version_obj.save()

    return JsonResponse({
        'message': f'Policy "{title}" v{version} uploaded successfully.',
        'version_id': version_obj.id,
        'changes': change_summary
    })

@require_GET
def policy_diffs(request, version_id):
    diffs = PolicyDiff.objects.filter(version_id=version_id).values('section_number', 'diff_text')
    return JsonResponse(list(diffs), safe=False)

@require_GET
def edit_policy(request, version_id=None):
    if version_id:
        version = get_object_or_404(PolicyVersion, id=version_id)
        sections = version.sections.filter(archived=False).values('section_number', 'content')
        context = {
            'version_id': version_id,
            'policy_title': version.policy.title,
            'version': version.version,
            'framework_id': version.policy.framework.id,
            'sections': list(sections),
            'frameworks': Framework.objects.all()
        }
    else:
        context = {
            'version_id': 0,
            'policy_title': '',
            'version': '',
            'framework_id': None,
            'sections': [],
            'frameworks': Framework.objects.all()
        }
    return render(request, 'editor.html', context)

@csrf_exempt
@require_POST
def generate_pdf(request):
    try:
        data = json.loads(request.body)
        version_id = data.get('version_id')
        title = data.get('title')
        version = data.get('version')
        framework_id = data.get('framework_id')
        sections = data.get('sections')
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        return JsonResponse({'error': f'Invalid input: {str(e)}'}, status=400)

    try:
        framework = Framework.objects.get(id=framework_id)
    except Framework.DoesNotExist:
        return JsonResponse({'error': 'Framework not found'}, status=404)

    policy, _ = Policy.objects.get_or_create(framework=framework, title=title)
    version_obj, created = PolicyVersion.objects.get_or_create(
        policy=policy,
        version=version,
        defaults={'uploaded_file': None}
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(version, styles['Heading1']))
    story.append(Paragraph(title, styles['Heading2']))

    for section in sections:
        section_number = section.get('section_number')
        content = section.get('content')
        story.append(Paragraph(f"{section_number}", styles['Heading3']))
        story.append(Paragraph(content, styles['Normal']))

    doc.build(story)
    pdf_data = buffer.getvalue()
    buffer.close()

    from django.core.files.base import ContentFile
    version_obj.uploaded_file.save(f"{title}_{version}.pdf", ContentFile(pdf_data))
    version_obj.save()

    existing_sections = PolicySection.objects.filter(version=version_obj)
    existing_section_map = {s.section_number: s for s in existing_sections}
    existing_sections.update(archived=True)

    prev_versions = PolicyVersion.objects.filter(policy=policy).exclude(id=version_obj.id).order_by('-created_at')
    old_sections = {}
    if prev_versions.exists():
        prev = prev_versions.first()
        old_sections = {s.section_number: s.content for s in prev.sections.all()}

    for section in sections:
        sec_num = section.get('section_number')
        content = section.get('content')
        section_obj = existing_section_map.get(sec_num)
        if section_obj:
            section_obj.content = content
            section_obj.archived = False
            section_obj.save()
        else:
            PolicySection.objects.create(
                version=version_obj,
                section_number=sec_num,
                content=content,
                archived=False
            )

        old_content = old_sections.get(sec_num, "")
        if old_content.strip() != content.strip():
            diff = '\n'.join(difflib.unified_diff(
                old_content.splitlines(),
                content.splitlines(),
                fromfile=f'{prev.version}:{sec_num}' if prev_versions.exists() else 'original',
                tofile=f'{version}:{sec_num}',
                lineterm=''
            ))
            PolicyDiff.objects.create(version=version_obj, section_number=sec_num, diff_text=diff)

    return JsonResponse({
        'message': f'Policy "{title}" v{version} generated and saved successfully.',
        'version_id': version_obj.id
    })

@csrf_exempt
def policy_change_history(request, policy_id):
    policy = get_object_or_404(Policy, id=policy_id)
    versions = PolicyVersion.objects.filter(policy=policy).order_by('-created_at')
    
    history = []
    for version in versions:
        history.append({
            'version': version.version,
            'created_at': version.created_at.isoformat(),
            'changes': version.change_summary,
            'version_id': version.id
        })
    
    return JsonResponse({'policy': policy.title, 'history': history})