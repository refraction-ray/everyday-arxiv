from datetime import date

from arxiv_daily.arxiv_client import parse_search_html


def test_html_parser_excludes_revisions_from_submitted_date_batch():
    html = """
    <ol>
      <li class="arxiv-result">
        <p class="list-title is-inline-block">
          <a href="https://arxiv.org/abs/2512.18995v2">arXiv:2512.18995</a>
        </p>
        <p class="title is-5 mathjax">DeepQuantum</p>
        <p class="authors"><a>Author One</a></p>
        <div class="tags"><span class="tag is-small">quant-ph</span></div>
        <p class="abstract mathjax">Abstract: Revised software paper.</p>
        <p class="is-size-7">
          <span class="has-text-weight-semibold">Submitted</span> 14 May, 2026;
          <span class="has-text-weight-semibold">v1</span> submitted 21 December, 2025;
        </p>
      </li>
    </ol>
    """

    papers = parse_search_html(html, target_date=date(2026, 5, 14))

    assert papers == []


def test_html_parser_keeps_first_submissions_from_submitted_date_batch():
    html = """
    <ol>
      <li class="arxiv-result">
        <p class="list-title is-inline-block">
          <a href="https://arxiv.org/abs/2605.12345v1">arXiv:2605.12345</a>
        </p>
        <p class="title is-5 mathjax">New Quantum Paper</p>
        <p class="authors"><a>Author One</a><a>Author Two</a></p>
        <div class="tags"><span class="tag is-small">quant-ph</span></div>
        <p class="abstract mathjax">Abstract: First submission.</p>
        <p class="is-size-7">
          <span class="has-text-weight-semibold">Submitted</span> 14 May, 2026;
          <span class="has-text-weight-semibold">v1</span> submitted 14 May, 2026;
        </p>
      </li>
    </ol>
    """

    papers = parse_search_html(html, target_date=date(2026, 5, 14))

    assert len(papers) == 1
    assert papers[0].arxiv_id == "2605.12345"
    assert papers[0].summary == "First submission."
    assert papers[0].published.startswith("2026-05-14")
    assert papers[0].updated.startswith("2026-05-14")
