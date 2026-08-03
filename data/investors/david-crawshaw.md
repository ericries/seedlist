---
check_size: ''
firm: ''
last_researched: 2026-08-03
last_verified_investment:
  company: exe.dev
  date: ~2026
  round: Co-founder
location: Berkeley, California
name: David Crawshaw
role: Co-Founder & CEO, exe.dev; Co-Founder, Tailscale
sector_focus:
- developer-tools
- infrastructure
- ai
- cloud-infrastructure
slug: david-crawshaw
social:
  bluesky: '@crawshaw.io'
  github: crawshaw
  linkedin: linkedin.com/in/crawshaw
  twitter: '@davidcrawshaw'
  website: https://crawshaw.io
stage_focus: []
status: published
type: individual
---

## Background

David Crawshaw is a systems engineer, co-founder of Tailscale, and co-founder & CEO of exe.dev. He is based in Berkeley, California [^1]. He previously worked at Google as a Staff Software Engineer, where he specialized in petabyte-scale logs processing, implemented TCP/IP networking for Fuchsia, and led the port of the Go programming language to iOS and Android [^1][^2]. He was a member of the Go language contributor team, with commits to golang.org, and presented "Go Build Modes" at GopherCon 2017 [^2]. He left Google in March 2018 [^3].

In 2019 Crawshaw co-founded Tailscale — the WireGuard-based mesh networking company headquartered in Toronto — alongside Avery Pennarun, David Carney, and Brad Fitzpatrick [^4]. He served as Tailscale's founding CTO. In a February 2025 interview on the Changelog podcast, Crawshaw stated: "I stepped back from the CTO last year" and described spending his time "exploring sort of new product spaces, things that can be done, both inside and outside of Tailscale" [^5].

That exploration became exe.dev, a developer-and-agent-focused cloud infrastructure company where Crawshaw is co-founder and CEO. In April 2026, exe.dev announced a $25M Series A led by Amplify Partners with participation from CRV and Heavybit [^6][^7]. exe.dev's earlier internal work was described in Crawshaw's April 2026 post "Building a cloud" [^7].

Crawshaw writes regularly at crawshaw.io on topics including Go, SQLite, compiler optimization, agent-assisted programming, and cloud infrastructure design [^3]. His 2025 blog post "How I program with LLMs" was widely circulated in developer communities [^8].

**On investing activity:** Crawshaw is primarily an engineer, writer, and operating founder. No independently sourced public angel investments were found in this research pass. He is not listed in the swyx `devtools-angels` community registry [^9]. He is profiled here because his writing, technical influence in the Go / developer-tools ecosystem, and role as a repeat founder make him a meaningful node in the investor-adjacent graph — and because founders raising in developer-tools/infrastructure often seek him out as an advisor. If he has done private angel checks, they are not publicly reported.

## Stated Thesis

Crawshaw has not published a formal investing thesis. As an operator, his stated product thesis at exe.dev is that AI agents and developers need the same primitive — a computer — and that current cloud abstractions get in the way. He has articulated this repeatedly:

- On why exe.dev exists: "Agents are trained on how developers work. They want exactly what we want. Full computers, understandable and stable building blocks, familiar systems wherever possible." [^6]
- On cloud VMs: "VMs are the wrong shape because they are tied to CPU/memory resources. I want to buy some CPUs, memory, and disk, and run VMs on it." [^7]
- On the current cloud pricing model: "The standard price for a GB of egress from a cloud provider is 10x what you pay racking a server in a normal data center." [^7]

At Tailscale, his stated technical thesis was that mesh networking and end-to-end encryption should replace perimeter security: "Both of these problems have much more elegant solutions if we can trust the network" [^10] and Tailscale is "by design, we never see your unencrypted traffic" [^10].

## Inferred Thesis

No verifiable public angel portfolio was found in this research pass, so a data-grounded inferred thesis cannot be constructed. Qualitative signals from Crawshaw's public writing and product work suggest he is most likely to be sympathetic to:

- **Developer-first infrastructure**: cloud, compute, storage, networking primitives designed for programmers rather than platform operators [^6][^7].
- **AI/agent tooling with a systems foundation**: he has described "an enormous amount of traditional engineering to do in front of LLMs" [^5] and has published extensively on programming with agents [^8].
- **Go and SQLite ecosystems**: he is a long-standing Go contributor [^2] and has open-sourced SQLite tooling on GitHub [^11].
- **Zero-trust networking and security-by-default**: consistent with his Tailscale co-founding thesis [^10].

This is a qualitative inference from writing and product choices, not from counted portfolio data. Founders should not treat this as a proxy for check-writing behavior.

## Portfolio

No independently verified angel investments were identified in this research pass. Crawshaw is a co-founder and operator at Tailscale and exe.dev; both are companies he built, not companies he backed as an outside investor.

| Company | Year | Stage | Role | Source |
|---------|------|-------|------|--------|
| Tailscale | 2019 | Co-founder | Co-Founder, ex-CTO | [^4] |
| exe.dev | 2026 | Co-founder | Co-Founder, CEO | [^6][^7] |

If you have documentation of angel investments by David Crawshaw (SEC filings, cap-table disclosures, or press coverage naming him personally as an investor), please submit a source via the pending-sources workflow.

## In Their Own Words

**On agents needing computers (exe.dev Series A announcement):**
> "Agents are trained on how developers work. They want exactly what we want. Full computers, understandable and stable building blocks, familiar systems wherever possible." [^6]

**On the shape of cloud VMs:**
> "VMs are the wrong shape because they are tied to CPU/memory resources. I want to buy some CPUs, memory, and disk, and run VMs on it." [^7]

**On egress pricing:**
> "The standard price for a GB of egress from a cloud provider is 10x what you pay racking a server in a normal data center." [^7]

**On stepping back from Tailscale CTO:**
> "I stepped back from the CTO last year." [^5]
>
> "I am spending my time exploring sort of new product spaces, things that can be done, both inside and outside of Tailscale." [^5]

**On the current state of AI-assisted coding (Feb 2026):**
> "In February this year, the latest Opus model can write nine tenths of my code." [^8]

**On the demise of the IDE in his workflow:**
> "In 2021, the IDE had won. In 2026, I don't use an IDE any more." [^8]
>
> "The only IDE-like feature I use today is go-to-def, which neovim is capable of with little configuration." [^8]

**On model selection:**
> "If you try some penny-saving cheap model like Sonnet, or a second rate local model, you do worse than waste your time." [^8]
>
> "You will not know what models will be capable of unless you use the best." [^8]

**On engineering LLM products:**
> "There has to be a way to make this easier. And my main conclusion from all of that is there's an enormous amount of traditional engineering to do in front of LLMs to get there." [^5]
>
> "They are actually extremely hard to turn into products, and to get those details right, in a general sense, for shipping to users." [^5]

**On chat interfaces:**
> "Chat is currently our primary user interface on the models, and it's not the best interface for most things." [^5]

**On the Tailscale founding thesis (2021 interview):**
> "Both of these problems have much more elegant solutions if we can trust the network." [^10]
>
> "by design, we never see your unencrypted traffic" [^10]

**On startups and language choice (ELC podcast):**
> "If you're a pre-seed startup in the Bay Area and you are trying to ship something to your first few customers and you ship with 40-something languages, then you've made a mistake, but it's not necessarily true that a large company has made that mistake." [^12]

**On his craft (Uses This interview):**
> "I like to write code and help others write code." [^13]

## What Founders Say

No independently sourced founder testimonials found. Crawshaw does not appear to have a publicly documented angel portfolio, and no third-party founder quotes describing him as an investor or advisor were surfaced in this research pass.

## Sources

[^1]: Crunchbase, "David Crawshaw – CTO and Co-Founder @ Tailscale," accessed August 2026. https://www.crunchbase.com/person/david-crawshaw
[^2]: Google Go language contributors list, accessed August 2026. https://go.dev/CONTRIBUTORS
[^3]: crawshaw.io blog index, accessed August 2026. https://crawshaw.io/blog/
[^4]: Wikipedia, "Tailscale," accessed August 2026. https://en.wikipedia.org/wiki/Tailscale
[^5]: Changelog Interviews #629, "Programming with LLMs featuring David Crawshaw," accessed August 2026. https://changelog.com/podcast/629
[^6]: exe.dev blog, "Series A for exe.dev," April 22, 2026, accessed August 2026. https://blog.exe.dev/series-a
[^7]: David Crawshaw, "Building a cloud," crawshaw.io, April 22, 2026, accessed August 2026. https://crawshaw.io/blog/building-a-cloud
[^8]: David Crawshaw, "Eight more months of agents," crawshaw.io, February 8, 2026, accessed August 2026. https://crawshaw.io/blog/eight-more-months-of-agents
[^9]: swyx, "devtools-angels" GitHub registry, accessed August 2026 (Crawshaw not listed). https://github.com/swyxio/devtools-angels
[^10]: Tailscale blog, "We all have to do a better job managing our infrastructure" (Cybernews interview with David Crawshaw), accessed August 2026. https://tailscale.com/blog/cybernews-interview
[^11]: David Crawshaw GitHub profile, accessed August 2026. https://github.com/crawshaw
[^12]: Engineering Leadership Community podcast, "Rapid prototyping & developing your product instinct" with David Crawshaw, accessed August 2026. https://sfelc.com/podcasts/rapid-prototyping-and-developing-your-product-instinct-david-crawshaw-tailscale
[^13]: Uses This, "David Crawshaw" interview, accessed August 2026. https://usesthis.com/interviews/david.crawshaw/