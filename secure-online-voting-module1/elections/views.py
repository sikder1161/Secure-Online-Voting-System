from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import CandidateForm, ElectionForm
from .models import (
    Candidate,
    Election,
    VoterEligibility,
    VoterParticipation,
)
from .services import cast_ballot


# Check whether the user is an Election Administrator
def election_admin(user):
    return (
        user.is_authenticated
        and user.is_active
        and user.role == user.Role.ELECTION_ADMIN
    )


# FR5 - Election List
@login_required
def election_list(request):
    if election_admin(request.user):
        qs = Election.objects.all()
    else:
        qs = Election.objects.exclude(
            status=Election.Status.DRAFT
        )

    return render(
        request,
        'elections/list.html',
        {
            'elections': qs,
            'is_election_admin': election_admin(request.user),
        }
    )


# FR5 - Create Election
@login_required
def election_create(request):
    if not election_admin(request.user):
        return HttpResponseForbidden(
            'Election administrator role required.'
        )

    form = ElectionForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        election = form.save(commit=False)

        election.created_by = request.user
        election.status = Election.Status.DRAFT

        election.save()

        messages.success(
            request,
            'Election created.'
        )

        return redirect(
            'elections:detail',
            pk=election.pk
        )

    return render(
        request,
        'elections/form.html',
        {
            'form': form,
            'heading': 'Create election',
        }
    )


# Election Details + Voter Name Dropdown
@login_required
def election_detail(request, pk):
    election = get_object_or_404(
        Election,
        pk=pk
    )

    is_admin = election_admin(request.user)

    # Draft elections are visible only to election admins
    if election.status == Election.Status.DRAFT and not is_admin:
        raise Http404

    # Load voter names instead of asking for manual user IDs
    if is_admin:
        voters = get_user_model().objects.filter(
            role='VOTER',
            is_active=True
        ).order_by(
            'first_name',
            'last_name',
            'username'
        )
    else:
        voters = get_user_model().objects.none()

    # Check election-specific eligibility
    eligibility = VoterEligibility.objects.filter(
        election=election,
        voter=request.user,
        decision='APPROVED'
    ).exists()

    # Check whether the voter has already voted
    has_voted = VoterParticipation.objects.filter(
        election=election,
        voter=request.user
    ).exists()

    return render(
        request,
        'elections/detail.html',
        {
            'election': election,
            'is_election_admin': is_admin,
            'eligible': eligibility,
            'has_voted': has_voted,
            'voters': voters,
        }
    )


# FR6 - Add Candidate
@login_required
def candidate_add(request, pk):
    election = get_object_or_404(
        Election,
        pk=pk
    )

    if not election_admin(request.user):
        return HttpResponseForbidden(
            'Election administrator role required.'
        )

    if not election.can_edit_candidates:
        messages.error(
            request,
            'Candidates are locked outside draft preparation.'
        )
        return redirect(
            'elections:detail',
            pk=pk
        )

    form = CandidateForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        candidate = form.save(commit=False)
        candidate.election = election

        try:
            candidate.full_clean()
            candidate.save()

        except ValidationError as exc:
            form.add_error(None, exc)

        else:
            messages.success(
                request,
                'Candidate added successfully.'
            )

            return redirect(
                'elections:detail',
                pk=pk
            )

    return render(
        request,
        'elections/form.html',
        {
            'form': form,
            'heading': 'Add candidate',
        }
    )


# FR6 - Edit Candidate
@login_required
def candidate_edit(request, pk):
    candidate = get_object_or_404(
        Candidate,
        pk=pk
    )

    if not election_admin(request.user):
        return HttpResponseForbidden(
            'Election administrator role required.'
        )

    if not candidate.election.can_edit_candidates:
        return HttpResponseForbidden(
            'Candidate changes are locked.'
        )

    form = CandidateForm(
        request.POST or None,
        instance=candidate
    )

    if request.method == 'POST' and form.is_valid():
        candidate = form.save(commit=False)

        try:
            candidate.full_clean()
            candidate.save()

        except ValidationError as exc:
            form.add_error(None, exc)

        else:
            messages.success(
                request,
                'Candidate updated successfully.'
            )

            return redirect(
                'elections:detail',
                pk=candidate.election_id
            )

    return render(
        request,
        'elections/form.html',
        {
            'form': form,
            'heading': 'Edit candidate',
        }
    )


# FR6 - Remove Candidate
@login_required
@require_POST
def candidate_remove(request, pk):
    candidate = get_object_or_404(
        Candidate,
        pk=pk
    )

    if not election_admin(request.user):
        return HttpResponseForbidden(
            'Election administrator role required.'
        )

    if not candidate.election.can_edit_candidates:
        return HttpResponseForbidden(
            'Candidate changes are locked.'
        )

    election_id = candidate.election_id

    candidate.delete()

    messages.success(
        request,
        'Candidate removed successfully.'
    )

    return redirect(
        'elections:detail',
        pk=election_id
    )


# FR5 - Finalize Election Schedule
@login_required
@require_POST
def schedule_election(request, pk):
    election = get_object_or_404(
        Election,
        pk=pk
    )

    if not election_admin(request.user):
        return HttpResponseForbidden(
            'Election administrator role required.'
        )

    if not election.can_edit_candidates:
        return HttpResponseForbidden(
            'Election preparation has ended.'
        )

    if not election.candidates.exists():
        messages.error(
            request,
            'Add at least one candidate first.'
        )

    else:
        election.status = Election.Status.SCHEDULED

        election.save(
            update_fields=['status']
        )

        messages.success(
            request,
            'Election scheduled; candidate list is locked.'
        )

    return redirect(
        'elections:detail',
        pk=pk
    )


# Election-Specific Voter Eligibility
@login_required
@require_POST
def approve_voter(request, pk):
    election = get_object_or_404(
        Election,
        pk=pk
    )

    # Only election administrators can approve voters
    if not election_admin(request.user):
        return HttpResponseForbidden(
            'Election administrator role required.'
        )

    # Eligibility changes are allowed during preparation only
    if (
        election.status != Election.Status.DRAFT
        or timezone.now() >= election.starts_at
    ):
        return HttpResponseForbidden(
            'Eligibility decisions are locked after preparation.'
        )

    # Read selected voter ID from the name dropdown
    voter_id = request.POST.get(
        'voter_id', ''
    ).strip()

    # Validate submitted ID
    if not voter_id.isdigit():
        messages.error(
            request,
            'Please select a valid voter.'
        )

        return redirect(
            'elections:detail',
            pk=pk
        )

    # Find the selected active voter
    voter = get_user_model().objects.filter(
        pk=int(voter_id),
        role='VOTER',
        is_active=True
    ).first()

    # Handle missing or invalid voter
    if voter is None:
        messages.error(
            request,
            'Selected voter was not found. '
            'Please select a voter from the list.'
        )

        return redirect(
            'elections:detail',
            pk=pk
        )

    # Verify Module 1 eligibility
    if not getattr(
        getattr(voter, 'voter_profile', None),
        'can_vote',
        False
    ):
        messages.error(
            request,
            'Voter must satisfy basic Module 1 eligibility first.'
        )

        return redirect(
            'elections:detail',
            pk=pk
        )

    # Get administrator's decision
    decision = request.POST.get('decision')

    if decision not in ('APPROVED', 'REJECTED'):
        return HttpResponseForbidden(
            'Invalid decision.'
        )

    # Create or update election-specific eligibility
    VoterEligibility.objects.update_or_create(
        election=election,
        voter=voter,
        defaults={
            'decision': decision,
            'reviewed_by': request.user,
            'reviewed_at': timezone.now(),
        }
    )

    messages.success(
        request,
        'Election-specific voter decision saved.'
    )

    return redirect(
        'elections:detail',
        pk=pk
    )


# FR7 + FR8 - Secure Vote Casting
@login_required
@require_POST
def vote(request, pk):
    election = get_object_or_404(
        Election,
        pk=pk
    )

    try:
        cast_ballot(
            voter=request.user,
            election_id=election.pk,
            candidate_id=request.POST.get('candidate')
        )

    except (ValidationError, ValueError, TypeError) as exc:

        if isinstance(exc, ValidationError):
            error_message = '; '.join(exc.messages)
        else:
            error_message = 'Invalid vote request.'

        messages.error(
            request,
            error_message
        )

        return redirect(
            'elections:detail',
            pk=pk
        )

    # Confirmation must not reveal the selected candidate
    return render(
        request,
        'elections/confirmation.html',
        {
            'election': election,
        }
    )

# FR5 - Edit Election
@login_required
def election_edit(request, pk):
    election = get_object_or_404(Election, pk=pk)

    if not election_admin(request.user):
        return HttpResponseForbidden(
            "Election administrator role required."
        )

    # Only draft elections can be edited before voting begins.
    if (
        election.status != Election.Status.DRAFT
        or timezone.now() >= election.starts_at
    ):
        return HttpResponseForbidden(
            "This election can no longer be edited."
        )

    form = ElectionForm(
        request.POST or None,
        instance=election
    )

    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        updated.status = Election.Status.DRAFT

        try:
            updated.full_clean()
            updated.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Election updated successfully.")
            return redirect("elections:detail", pk=election.pk)

    return render(
        request,
        "elections/form.html",
        {
            "form": form,
            "heading": "Edit Election",
        }
    )


# FR5 - Delete Election
@login_required
@require_POST
def election_delete(request, pk):
    election = get_object_or_404(Election, pk=pk)

    if not election_admin(request.user):
        return HttpResponseForbidden(
            "Election administrator role required."
        )

    # Do not delete elections after preparation.
    if (
        election.status != Election.Status.DRAFT
        or timezone.now() >= election.starts_at
    ):
        return HttpResponseForbidden(
            "Only future draft elections can be deleted."
        )

    # Do not delete an election that contains accepted votes.
    if VoterParticipation.objects.filter(election=election).exists():
        return HttpResponseForbidden(
            "Cannot delete an election with recorded votes."
        )

    # Ballots must also be checked separately.
    if election.encrypted_votes.exists():
        return HttpResponseForbidden(
            "Cannot delete an election with encrypted ballots."
        )

    election.delete()

    messages.success(request, "Draft election deleted successfully.")
    return redirect("elections:list")

# FR5 - Edit Election
@login_required
def election_edit(request, pk):
    election = get_object_or_404(Election, pk=pk)

    if not election_admin(request.user):
        return HttpResponseForbidden(
            "Election administrator role required."
        )

    if (
        election.status != Election.Status.DRAFT
        or timezone.now() >= election.starts_at
    ):
        return HttpResponseForbidden(
            "This election can no longer be edited."
        )

    form = ElectionForm(
        request.POST or None,
        instance=election
    )

    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        updated.status = Election.Status.DRAFT

        try:
            updated.full_clean()
            updated.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(
                request,
                "Election updated successfully."
            )
            return redirect("elections:detail", pk=election.pk)

    return render(
        request,
        "elections/form.html",
        {
            "form": form,
            "heading": "Edit Election",
        }
    )


# FR5 - Delete Election
@login_required
@require_POST
def election_delete(request, pk):
    election = get_object_or_404(Election, pk=pk)

    if not election_admin(request.user):
        return HttpResponseForbidden(
            "Election administrator role required."
        )

    if (
        election.status != Election.Status.DRAFT
        or timezone.now() >= election.starts_at
    ):
        return HttpResponseForbidden(
            "Only future draft elections can be deleted."
        )

    if VoterParticipation.objects.filter(election=election).exists():
        return HttpResponseForbidden(
            "Cannot delete an election with recorded votes."
        )

    # Also check encrypted ballots before deleting.
    from .models import EncryptedVote

    if EncryptedVote.objects.filter(election=election).exists():
        return HttpResponseForbidden(
            "Cannot delete an election with encrypted ballots."
        )

    election.delete()

    messages.success(
        request,
        "Draft election deleted successfully."
    )
    return redirect("elections:list")

