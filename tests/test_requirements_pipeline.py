import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scout_archive.requirements_pipeline import (
    HtmlExtractor,
    RawRequirementItem,
    SemanticProcessor,
)


class SemanticProcessorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.extractor = HtmlExtractor()
        self.processor = SemanticProcessor()

    def test_groups_flattened_option_blocks_and_nested_lettered_children(self) -> None:
        html = """
        <div class="mb-requirement-container">
          <div class="mb-requirement-item">
            <div class="mb-requirement-parent mb-requirement-id-6">
              <span class="mb-requirement-listnumber">6.</span>
              Complete ONE of the following options:
            </div>
            <ul class="mb-requirement-children-list">
              <li class="mb-requirement-child"><strong>Option A - Beef Cattle.</strong> Do ALL of the following:</li>
              <li class="mb-requirement-child">1. Visit a farm.</li>
              <li class="mb-requirement-child">2. Sketch a plan.</li>
              <li class="mb-requirement-child">3. Make a sketch.</li>
              <li class="mb-requirement-child">4. Do ONE of the following:</li>
              <li class="mb-requirement-child">(a) Raise an animal.</li>
              <li class="mb-requirement-child">(b) Visit a ranch.</li>
              <li class="mb-requirement-child"><strong>Option B - Dairy Cattle.</strong> Do ALL of the following:</li>
              <li class="mb-requirement-child">1. Explain feed differences.</li>
            </ul>
          </div>
        </div>
        """

        requirements = self.processor.process(self.extractor.extract(html))

        self.assertEqual(requirements[0].label, "6")
        self.assertEqual(requirements[0].node_kind, "instruction_container")
        self.assertEqual(requirements[0].requires_response, False)
        self.assertEqual(
            [child.requirement_path for child in requirements[0].sub_requirements],
            ["6.option-a", "6.option-b"],
        )

        option_a = requirements[0].sub_requirements[0]
        self.assertEqual(option_a.node_kind, "option_container")
        self.assertEqual(
            [child.label for child in option_a.sub_requirements], ["1", "2", "3", "4"]
        )
        self.assertEqual(
            [child.label for child in option_a.sub_requirements[3].sub_requirements],
            ["a", "b"],
        )
        self.assertEqual(
            option_a.sub_requirements[3].sub_requirements[1].requirement_path,
            "6.option-a.4.b",
        )

    def test_nests_numbered_choices_under_alpha_list_introducer(self) -> None:
        html = """
        <div class="mb-requirement-container">
          <div class="mb-requirement-item">
            <div class="mb-requirement-parent mb-requirement-id-5">
              <span class="mb-requirement-listnumber">5.</span>
              Do the following:
            </div>
            <ul class="mb-requirement-children-list">
              <li class="mb-requirement-child">(a) Tell what you learned.</li>
              <li class="mb-requirement-child">(b) Do ONE of the following:</li>
              <li class="mb-requirement-child">1. Observe a colony.</li>
              <li class="mb-requirement-child">2. Study a hive.</li>
            </ul>
          </div>
        </div>
        """

        requirements = self.processor.process(self.extractor.extract(html))

        child_b = requirements[0].sub_requirements[1]
        self.assertEqual(child_b.requirement_path, "5.b")
        self.assertEqual(
            [child.requirement_path for child in child_b.sub_requirements],
            ["5.b.1", "5.b.2"],
        )

    def test_keeps_resumed_alpha_sibling_after_numbered_choices(self) -> None:
        html = """
        <div class="mb-requirement-container">
          <div class="mb-requirement-item">
            <div class="mb-requirement-parent mb-requirement-id-6">
              <span class="mb-requirement-listnumber">6.</span>
              Do the following:
            </div>
            <ul class="mb-requirement-children-list">
              <li class="mb-requirement-child">(a) Share what makes you unique.</li>
              <li class="mb-requirement-child">(b) Discuss ONE of the following:</li>
              <li class="mb-requirement-child">1. Option one discussion.</li>
              <li class="mb-requirement-child">2. Option two discussion.</li>
              <li class="mb-requirement-child">(c) Explain what you learned.</li>
            </ul>
          </div>
        </div>
        """

        requirements = self.processor.process(self.extractor.extract(html))

        children = requirements[0].sub_requirements
        self.assertEqual(
            [child.requirement_path for child in children], ["6.a", "6.b", "6.c"]
        )
        child_b = children[1]
        self.assertEqual(
            [child.requirement_path for child in child_b.sub_requirements],
            ["6.b.1", "6.b.2"],
        )
        self.assertEqual(child_b.sub_requirements[1].node_kind, "action_requirement")
        self.assertEqual(child_b.sub_requirements[1].requires_response, True)

    def test_option_prefixed_action_requirements_stay_answerable(self) -> None:
        html = """
        <div class="mb-requirement-container">
          <div class="mb-requirement-item">
            <div class="mb-requirement-parent mb-requirement-id-4">
              <span class="mb-requirement-listnumber">4.</span>
              Conduct THREE experiments, selecting from the following options.
            </div>
            <ul class="mb-requirement-children-list">
              <li class="mb-requirement-child"><strong>Option A: Motion.</strong> Make and test a car.</li>
              <li class="mb-requirement-child"><strong>Option B: Momentum.</strong> Drop stacked balls.</li>
            </ul>
          </div>
        </div>
        """

        requirements = self.processor.process(self.extractor.extract(html))

        children = requirements[0].sub_requirements
        self.assertEqual(len(children), 2)
        self.assertEqual(children[0].node_kind, "action_requirement")
        self.assertEqual(children[0].requires_response, True)
        self.assertEqual(children[0].requirement_path, "4.option-a")
        self.assertEqual(children[1].requirement_path, "4.option-b")

    def test_groups_flat_option_headings_with_section_tasks(self) -> None:
        html = """
        <div class="mb-requirement-container">
          <div class="mb-requirement-item">
            <div class="mb-requirement-parent mb-requirement-id-4">
              <span class="mb-requirement-listnumber">4.</span>
              Complete ALL of the following for the option you selected:
            </div>
            <ul class="mb-requirement-children-list">
              <li class="mb-requirement-child"><strong>Option A&mdash;Triathlon.</strong></li>
              <li class="mb-requirement-child">1. <b>Swimming</b></li>
              <li class="mb-requirement-child">(a) Earn the Swimming merit badge.</li>
              <li class="mb-requirement-child">(b) Explain Safe Swim Defense.</li>
              <li class="mb-requirement-child">2. <b>Biking</b></li>
              <li class="mb-requirement-child">(a) Explain how to ride predictably.</li>
              <li class="mb-requirement-child"><strong>Option B&mdash;Duathlon.</strong></li>
              <li class="mb-requirement-child">1. <b>Biking</b></li>
              <li class="mb-requirement-child">(a) Check bicycle safety.</li>
            </ul>
          </div>
        </div>
        """

        requirements = self.processor.process(self.extractor.extract(html))

        parent = requirements[0]
        self.assertEqual(parent.node_kind, "instruction_container")
        self.assertEqual(parent.requires_response, False)
        self.assertEqual(
            [child.requirement_path for child in parent.sub_requirements],
            ["4.option-a", "4.option-b"],
        )

        option_a = parent.sub_requirements[0]
        self.assertEqual(option_a.node_kind, "option_container")
        self.assertEqual(option_a.requires_response, False)
        self.assertEqual(
            [child.requirement_path for child in option_a.sub_requirements],
            ["4.option-a.1", "4.option-a.2"],
        )
        self.assertEqual(
            option_a.sub_requirements[0].node_kind, "instruction_container"
        )
        self.assertEqual(
            [
                child.requirement_path
                for child in option_a.sub_requirements[0].sub_requirements
            ],
            ["4.option-a.1.a", "4.option-a.1.b"],
        )

    def test_promotes_link_only_support_children_to_resources(self) -> None:
        parent = RawRequirementItem(
            id="7",
            content_nodes=self.extractor.extract_nodes(
                "Find out about a career in this field."
            ),
            sub_requirements=[
                RawRequirementItem(
                    id="U",
                    content_nodes=self.extractor.extract_nodes(
                        '<strong><a href="https://example.com/careers">Career resource</a></strong> '
                        '<a href="https://example.com/jobs">Job list</a>'
                    ),
                )
            ],
        )

        requirements = self.processor.process([parent])

        self.assertEqual(requirements[0].sub_requirements, [])
        self.assertEqual(
            [(resource.title, resource.url) for resource in requirements[0].resources],
            [
                ("Career resource", "https://example.com/careers"),
                ("Job list", "https://example.com/jobs"),
            ],
        )

    def test_splits_collapsed_inline_lettered_requirements(self) -> None:
        parent = RawRequirementItem(
            id="1",
            content_nodes=self.extractor.extract_nodes("Do the following:"),
            sub_requirements=[
                RawRequirementItem(
                    id="a",
                    content_nodes=self.extractor.extract_nodes(
                        "<br><strong></strong>(a) Discuss safety. "
                        "(b) Explain what you learned."
                    ),
                )
            ],
        )

        requirements = self.processor.process([parent])

        self.assertEqual(
            [child.label for child in requirements[0].sub_requirements], ["a", "b"]
        )
        self.assertEqual(requirements[0].sub_requirements[0].text, "Discuss safety.")
        self.assertEqual(
            requirements[0].sub_requirements[1].text, "Explain what you learned."
        )

    def test_does_not_split_parenthetical_numeric_references(self) -> None:
        parent = RawRequirementItem(
            id="5",
            content_nodes=self.extractor.extract_nodes("5. Do the following:"),
            sub_requirements=[
                RawRequirementItem(
                    id="b",
                    content_nodes=self.extractor.extract_nodes(
                        "(b) Do ONE of the following:"
                    ),
                    sub_requirements=[
                        RawRequirementItem(
                            id="1",
                            content_nodes=self.extractor.extract_nodes(
                                "1. Observe a colony."
                            ),
                        ),
                        RawRequirementItem(
                            id="2",
                            content_nodes=self.extractor.extract_nodes(
                                "2. Study a hive. (If allergic, pick option (1) above.)"
                            ),
                        ),
                    ],
                )
            ],
        )

        requirements = self.processor.process([parent])

        child_b = requirements[0].sub_requirements[0]
        self.assertEqual(
            [child.requirement_path for child in child_b.sub_requirements],
            ["5.b.1", "5.b.2"],
        )
        self.assertEqual(
            child_b.sub_requirements[1].text,
            "Study a hive. (If allergic, pick option (1) above.)",
        )

    def test_promotes_single_inline_label_and_drops_empty_leaves(self) -> None:
        parent = RawRequirementItem(
            id="2",
            content_nodes=self.extractor.extract_nodes("Do the following:"),
            sub_requirements=[
                RawRequirementItem(
                    id="c",
                    content_nodes=self.extractor.extract_nodes(
                        "(c) Reflect on what you learned."
                    ),
                ),
                RawRequirementItem(
                    id="empty",
                    content_nodes=self.extractor.extract_nodes("<br>"),
                ),
            ],
        )

        requirements = self.processor.process([parent])

        self.assertEqual(
            [child.label for child in requirements[0].sub_requirements], ["c"]
        )
        self.assertEqual(
            requirements[0].sub_requirements[0].text,
            "Reflect on what you learned.",
        )

    def test_collapses_empty_passthrough_nodes_with_duplicate_label(self) -> None:
        parent = RawRequirementItem(
            id="2",
            content_nodes=self.extractor.extract_nodes("2. Do ONE of the following:"),
            sub_requirements=[
                RawRequirementItem(
                    id="a",
                    content_nodes=self.extractor.extract_nodes("(a)"),
                    sub_requirements=[
                        RawRequirementItem(
                            id="a",
                            content_nodes=self.extractor.extract_nodes(
                                "(a) Explain what happened."
                            ),
                        )
                    ],
                )
            ],
        )

        requirements = self.processor.process([parent])

        self.assertEqual(
            [child.requirement_path for child in requirements[0].sub_requirements],
            ["2.a"],
        )
        self.assertEqual(
            requirements[0].sub_requirements[0].text,
            "Explain what happened.",
        )

    def test_keeps_inline_numbered_body_list_with_existing_children(self) -> None:
        parent = RawRequirementItem(
            id="1",
            content_nodes=self.extractor.extract_nodes(
                "1. Select three professions from Group 1, then complete the following:"
                "<br><br><strong>Group 1:</strong><br>"
                "(1) Allopathic physician (MD)<br>"
                "(2) Osteopathic physician (DO)<br>"
                "(3) Podiatrist (DPM)"
            ),
            sub_requirements=[
                RawRequirementItem(
                    id="a",
                    content_nodes=self.extractor.extract_nodes(
                        "(a) Describe the roles these professionals play."
                    ),
                ),
                RawRequirementItem(
                    id="b",
                    content_nodes=self.extractor.extract_nodes(
                        "(b) Describe the education requirements."
                    ),
                ),
            ],
        )

        requirements = self.processor.process([parent])

        self.assertEqual(len(requirements), 1)
        self.assertEqual(requirements[0].label, "1")
        self.assertIn("(1) Allopathic physician", requirements[0].text)
        self.assertEqual(
            [child.requirement_path for child in requirements[0].sub_requirements],
            ["1.a", "1.b"],
        )

    def test_does_not_split_numbered_parenthetical_after_line_break(self) -> None:
        parent = RawRequirementItem(
            id="3",
            content_nodes=self.extractor.extract_nodes(
                "3. After completing requirement<br>"
                "(2) for the road biking option, do ONE of the following:"
            ),
            sub_requirements=[
                RawRequirementItem(
                    id="a",
                    content_nodes=self.extractor.extract_nodes("(a) Lay out a trip."),
                ),
                RawRequirementItem(
                    id="b",
                    content_nodes=self.extractor.extract_nodes(
                        "(b) Participate in an organized tour."
                    ),
                ),
            ],
        )

        requirements = self.processor.process([parent])

        self.assertEqual(len(requirements), 1)
        self.assertEqual(requirements[0].label, "3")
        self.assertIn("(2) for the road biking option", requirements[0].text)
        self.assertEqual(
            [child.requirement_path for child in requirements[0].sub_requirements],
            ["3.a", "3.b"],
        )

    def test_promotes_resumed_alpha_choice_from_nested_numeric_list(self) -> None:
        parent = RawRequirementItem(
            id="6",
            content_nodes=self.extractor.extract_nodes("6. Do ONE of the following:"),
            sub_requirements=[
                RawRequirementItem(
                    id="a",
                    content_nodes=self.extractor.extract_nodes(
                        "(a) Shoot one round of ONE of the following:"
                    ),
                    sub_requirements=[
                        RawRequirementItem(
                            id="1",
                            content_nodes=self.extractor.extract_nodes(
                                "1. First round."
                            ),
                        ),
                        RawRequirementItem(
                            id="2",
                            content_nodes=self.extractor.extract_nodes(
                                "2. Second round."
                            ),
                        ),
                        RawRequirementItem(
                            id="b",
                            content_nodes=self.extractor.extract_nodes(
                                "(b) Shoot an alternate round."
                            ),
                        ),
                    ],
                )
            ],
        )

        requirements = self.processor.process([parent])

        self.assertEqual(
            [child.requirement_path for child in requirements[0].sub_requirements],
            ["6.a", "6.b"],
        )
        self.assertEqual(
            [
                child.requirement_path
                for child in requirements[0].sub_requirements[0].sub_requirements
            ],
            ["6.a.1", "6.a.2"],
        )


if __name__ == "__main__":
    unittest.main()
