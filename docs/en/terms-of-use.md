# Obscura Text Writer Terms of Use

> **DRAFT.** This document is not in force and requires review by a lawyer familiar with Ukrainian and EU law. Until approved, it expresses the project author's intent rather than final legal terms. The Ukrainian version is authoritative: [Українська версія](../terms-of-use.md).

Revision: draft of 10 November 2026.

## 1. Scope

Obscura Text Writer (the "Application") is a local tool for writing fiction with the help of language models. The Application supports work on adult fiction, but it is built for **lawful** use.

The source code is distributed under [FSL-1.1-MIT](../../LICENSE); versions up to and including the `last-mit` tag remain available under the [MIT License](../licensing/MIT-previous-versions.txt). The name and logo are covered by the [name and logo policy](trademark-policy.md). These Terms do not change or restrict the code licence. They set the rules for using the Application and the ready-made builds (installers) distributed by the project author, and they apply to anyone who installs or runs such a build.

## 2. Age and lawfulness

2.1. Only persons who are at least 18 years old, or of the age of majority in their country if higher, may use the Application.

2.2. Users must use the Application only in accordance with the law of the European Union and of the country in which they reside or of which they are a citizen, including laws on sexual content, personal data protection, honour and dignity, copyright and criminal law.

2.3. The line between permitted and prohibited sexual content differs between countries. Users are solely responsible for ensuring that the texts they create and distribute comply with the law that applies to them.

## 3. Absolute prohibitions

Regardless of the law of the user's country, the Application must not be used to create, edit, evaluate or distribute:

3.1. any sexual or sexualised content involving minors, **including fictional characters** who are under 18 or are described or presented as minors;

3.2. sexual, degrading or defamatory content about identifiable real persons without their consent;

3.3. threats, harassment, incitement to violence or other unlawful acts against real persons or groups;

3.4. material that promotes or justifies terrorism or other crimes against humanity, beyond artistic treatment that does not break the law;

3.5. texts that infringe third-party intellectual property rights, or processing of other people's unpublished texts in breach of confidentiality obligations.

## 4. Cloud model providers

4.1. The Application sends fragments of works to third-party model providers (for example Venice or OpenRouter) only if the user has configured such a provider and their own access key.

4.2. These providers' terms of use and privacy policies apply separately and directly to the user. The Application is not intended to circumvent provider rules, and the user must not use it that way.

4.3. A provider may see, store or review submitted text under its own terms. The choice of provider and privacy level is the user's responsibility.

## 5. Local processing and responsibility

5.1. The Application runs on the user's device. The project author does not receive, see or control users' texts, settings or keys.

5.2. The user bears responsibility for the content of the texts they create, for their distribution and for compliance with the law.

5.3. The Application includes technical safeguards: story and scene age ratings and a check of the characters’ stated age before generating scenes with sexual content. They help users comply with these Terms but do not guarantee legal compliance and do not shift responsibility to the project author.

5.4. The Application is provided "as is", without warranty, as set out in the code licence (section 1) and applicable law.

## 6. Violations

If the project author learns that the Application is being used in breach of these Terms, they may refuse the violator support, access to updates and project services, and notify the competent authorities where required by law.

## 7. Changes

The project author may change these Terms. A new revision is published in the repository and on the project website with its date; material changes are shown in the Application on update.

## 8. Contact

Reports of violations and questions about these Terms: [CONTACT TO BE DEFINED].

---

### Drafting notes (remove before approval)

- Review with a lawyer: choice of governing law and jurisdiction; relation to Article 301(1) and Article 301-1 of the Criminal Code of Ukraine; scope of Directive 2011/93/EU regarding textual depictions and fictional characters; whether a separate DSA/GDPR clause is needed for the project website.
- Define the consent mechanism in ready-made builds: a first-run or installer screen confirming age and acceptance of the Terms; the accepted Terms revision is stored locally.
- Clause 5.3: the safeguards are implemented (#28). Generation does not start without a story rating; a scene with sexual content is not generated unless every participant’s card states an age of 18 or more. The age comes from the author’s record and is not verified, so false data bypasses the safeguard. Review with a lawyer whether the wording of 5.3 is sufficient.
