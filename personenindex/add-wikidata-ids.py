#!/usr/bin/env python3
"""
Script to fetch Wikidata IDs based on GND numbers and add them to listperson.xml
"""

import requests
import time
import xml.etree.ElementTree as ET
from typing import Optional

# TEI namespace
TEI_NS = {'tei': 'http://www.tei-c.org/ns/1.0'}
ET.register_namespace('', 'http://www.tei-c.org/ns/1.0')


def get_wikidata_id_from_gnd(gnd: str) -> Optional[str]:
    """
    Query Wikidata SPARQL endpoint to find Wikidata ID for a given GND number.

    Args:
        gnd: The GND identifier (e.g., "118500694")

    Returns:
        Wikidata ID (e.g., "Q456123") or None if not found
    """
    sparql_endpoint = "https://query.wikidata.org/sparql"

    # SPARQL query to find entity with given GND number
    query = f"""
    SELECT ?item WHERE {{
      ?item wdt:P227 "{gnd}".
    }}
    LIMIT 1
    """

    headers = {
        'User-Agent': 'GND-Wikidata-Matcher/1.0',
        'Accept': 'application/json'
    }

    try:
        response = requests.get(
            sparql_endpoint,
            params={'query': query, 'format': 'json'},
            headers=headers,
            timeout=10
        )
        response.raise_for_status()

        data = response.json()
        bindings = data.get('results', {}).get('bindings', [])

        if bindings:
            # Extract Wikidata ID from URI
            wikidata_uri = bindings[0]['item']['value']
            wikidata_id = wikidata_uri.split('/')[-1]
            return wikidata_id

        return None

    except requests.exceptions.RequestException as e:
        print(f"Error querying Wikidata for GND {gnd}: {e}")
        return None


def add_wikidata_ids_to_xml(input_file: str, output_file: str, delay: float = 1.0):
    """
    Process the TEI XML file and add Wikidata IDs based on GND numbers.

    Args:
        input_file: Path to input listperson.xml
        output_file: Path to output file with Wikidata IDs
        delay: Delay in seconds between API requests (to be polite)
    """
    # Parse the XML file
    tree = ET.parse(input_file)
    root = tree.getroot()

    # Find all person elements
    persons = root.findall('.//tei:person', TEI_NS)
    total_persons = len(persons)

    print(f"Found {total_persons} person entries")
    print("Starting Wikidata lookup...\n")

    added_count = 0
    skipped_count = 0
    not_found_count = 0

    for idx, person in enumerate(persons, 1):
        person_id = person.get('{http://www.w3.org/XML/1998/namespace}id', 'unknown')

        # Check if person already has Wikidata ID
        existing_wikidata = person.find('.//tei:idno[@type="wikidata"]', TEI_NS)
        if existing_wikidata is not None:
            print(f"[{idx}/{total_persons}] {person_id}: Already has Wikidata ID ({existing_wikidata.text}), skipping")
            skipped_count += 1
            continue

        # Get GND number
        gnd_element = person.find('.//tei:idno[@type="gnd"]', TEI_NS)
        if gnd_element is None or not gnd_element.text:
            print(f"[{idx}/{total_persons}] {person_id}: No GND number found, skipping")
            skipped_count += 1
            continue

        gnd = gnd_element.text.strip()
        print(f"[{idx}/{total_persons}] {person_id}: Looking up GND {gnd}...", end=' ')

        # Query Wikidata
        wikidata_id = get_wikidata_id_from_gnd(gnd)

        if wikidata_id:
            print(f"✓ Found {wikidata_id}")

            # Create new idno element for Wikidata
            wikidata_idno = ET.Element('{http://www.tei-c.org/ns/1.0}idno')
            wikidata_idno.set('type', 'wikidata')
            wikidata_idno.text = wikidata_id

            # Insert after GND idno
            gnd_index = list(person).index(gnd_element)
            person.insert(gnd_index + 1, wikidata_idno)

            added_count += 1
        else:
            print("✗ Not found")
            not_found_count += 1

        # Be polite to the Wikidata API
        if idx < total_persons:
            time.sleep(delay)

    # Write the updated XML
    tree.write(output_file, encoding='UTF-8', xml_declaration=True)

    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Total persons: {total_persons}")
    print(f"  Wikidata IDs added: {added_count}")
    print(f"  Already had Wikidata: {skipped_count}")
    print(f"  Not found in Wikidata: {not_found_count}")
    print(f"\nOutput written to: {output_file}")
    print(f"{'='*60}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Add Wikidata IDs to TEI listperson.xml based on GND numbers'
    )
    parser.add_argument(
        '-i', '--input',
        default='listperson.xml',
        help='Input XML file (default: listperson.xml)'
    )
    parser.add_argument(
        '-o', '--output',
        default='listperson-with-wikidata.xml',
        help='Output XML file (default: listperson-with-wikidata.xml)'
    )
    parser.add_argument(
        '-d', '--delay',
        type=float,
        default=1.0,
        help='Delay between API requests in seconds (default: 1.0)'
    )

    args = parser.parse_args()

    add_wikidata_ids_to_xml(args.input, args.output, args.delay)
