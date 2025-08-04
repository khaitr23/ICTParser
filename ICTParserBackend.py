from datetime import datetime
import re
import os
import csv
from collections import OrderedDict

timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
LOG_FILE = f"ICTParser_debug {timestamp}.txt"
DEBUG_MODE = False
if DEBUG_MODE:
    with open(LOG_FILE, "x") as logf:
        logf.write("ICTParser @ " + timestamp + "\n")

def log_debug(message):
    """
    Used for debugging, produces a debug/log file
    """
    if DEBUG_MODE:
        with open(LOG_FILE, "a") as logf:
            logf.write(message + "\n")

def parse_ict_log(filepath):
    """
    Parse a single ICT log file and return:
    - tester: str
    - serial: str
    - results: dict {column_name: measured_value}
    - limits: dict {column_name: (upper, lower)}
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
        #log_debug("File read: " + filepath)

    # Extract Tester and Serial from header
    batch_match = re.search(r'\{@BATCH\|([^\}]*)\}', text)
    tester = None
    if batch_match:
        batch_fields = batch_match.group(1).split('|')
        if len(batch_fields) > 8:
            tester = batch_fields[8].strip()

    # Serial: after 1st pipe in {@BTEST|...}
    btest_match = re.search(r'\{@BTEST\|([^\}]*)\}', text)
    serial = None
    if btest_match:
        btest_fields = btest_match.group(1).split('|')
        if len(btest_fields) > 0:
            serial = btest_fields[0].strip()

    results = OrderedDict()
    limits = dict()
    failures = []

    # Split into blocks
    blocks = re.split(r'\{@BLOCK\|', text)[1:]  # skip the header '@BATCH|...'
    for block in blocks:
        # block_name is before first '|'
        newline_index = block.find('\n')
        if newline_index == -1:
            block_name_full = block.strip()
            block_content = ''
        else:
            block_name_full = block[:newline_index].strip()
            block_content = block[newline_index+1:].strip()
        
        #Remove trailing '|00', '|01', etc. from the block name
        block_name = block_name_full.split('|')[0]
        
        #log_debug(f"Block: {block_name}\n{block_content}")

        # Find all measurements in block
        for mea_match in re.finditer(
            r'\{@A-[^|}]+\|(\d)\|([^\|{}]+?)(?:\|([^\{@]+?))?\{@LIM(\d)\|([^\}]+)\}\}',
            block_content
        ):
            passfail = mea_match.group(1)
            value = mea_match.group(2).strip()
            subname = mea_match.group(3)
            limtype = mea_match.group(4)
            lims = mea_match.group(5).split('|')

            # If there are more than 1 subtests in a block, we need to rename columns in that block
            if subname:
                colname = f"{block_name}_{subname.strip()}"
            else:
                colname = block_name

            if passfail == '0':
                results[colname] = value  # Only add passing tests to CSV
            else:
                                # collect failure info
                failures.append({
                    'file': filepath,
                    'block': block_name,
                    'test': colname,
                    'value': value
                })
                #log_debug(f"TEST FAILED: Block '{block_name}', Test '{colname}', Value '{value}' in file '{filepath}'")

            # Store limits (LL, UL)
            if limtype == '2':
                if len(lims) >= 2:
                    ul, ll = lims[0].strip(), lims[1].strip()
                else:
                    ul, ll = '', ''
            elif limtype == '3':
                if len(lims) >= 3:
                    ll, ul = lims[1].strip(), lims[2].strip()
                else:
                    ul, ll = '', ''
            else:
                ul, ll = '', ''
            limits[colname] = (ul, ll)

    #log_debug(f"Extracted columns: {list(results.keys())}")
    return tester, serial, results, limits, failures


def aggregate_results(filepaths):
    """
    Parse all files and aggregate results.
    Returns:
    - columns: list of all column names (Tester, Serial, ...)
    - rows: list of dicts for each board tested
    - limits: dict of {colname: (UL, LL)}
    """
    all_columns = set()
    all_limits = dict()
    all_failures = []
    rows = []

    for fp in filepaths:
        tester, serial, results, limits, failures = parse_ict_log(fp)
        all_failures.extend(failures)
        
        row = OrderedDict()
        row['Tester'] = tester
        row['Serial'] = serial
        for k, v in results.items():
            row[k] = v
            all_columns.add(k)
       
       # Merge limits
        for k, lim in limits.items():
            all_limits[k] = lim
        rows.append(row)

    # Sort columns: Tester, Serial, then others alphabetically
    sorted_columns = ['Tester', 'Serial'] + sorted(all_columns)
    return sorted_columns, rows, all_limits, all_failures

def write_csv(outfile, columns, rows, limits):
    """
    Write the results and limits to a CSV file.
    """
    with open(outfile, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Write header
        writer.writerow(columns)
        
        # Write data rows
        for row in rows:
            writer.writerow([row.get(col, '') for col in columns])

        # Write UL, LL, TOL rows
        ul_row = ['', 'UL'] + [limits.get(col, ('', ''))[0] for col in columns[2:]]
        ll_row = ['', 'LL'] + [limits.get(col, ('', ''))[1] for col in columns[2:]]
        tol_row = ['', 'TOL'] + [
            (str(float(ul) - float(ll)) if ul and ll else '') for ul, ll in [limits.get(col, ('', '')) for col in columns[2:]]
        ]
        writer.writerow(ul_row)
        writer.writerow(ll_row)
        writer.writerow(tol_row)

def write_failures_log(outfile, failures):
    """
    Write all failed-test entries to a CSV for review.
    """
    with open(outfile, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['File', 'Block', 'Test', 'Value'])
        for fx in failures:
            writer.writerow([fx['file'], fx['block'], fx['test'], fx['value']])

if __name__ == '__main__':
    # Place all log files in a folder, e.g. './logs/'
    log_folder = './logs/'

    # Rename csv file as required
    out_csv = 'ICT_Parser_Result.csv'

    filepaths = [os.path.join(log_folder, fn) for fn in os.listdir(log_folder) if not fn.startswith('.')]
    columns, rows, limits = aggregate_results(filepaths)
    write_csv(out_csv, columns, rows, limits)
    log_debug(f"CSV written to {out_csv}")