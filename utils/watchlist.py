import pandas as pd


def generate_watchlist(df: pd.DataFrame, group_by: str):
    filtered_df = df[df['mcap'] > 3e9].copy()

    # Group by industry_2, get top 10 by mcap, and create the formatted string with count
    def format_group(group):
        # Skip groups with only 1 item
        if len(group) <= 1:
            return group.index.astype(str)

        # Get top 10 by market cap
        top_10 = group.nlargest(10, 'mcap')
        # Join the tickers
        tickers = "+".join(top_10.index.astype(str))
        # Get total count in the filtered group
        total_count = len(group)
        return [f"{tickers}/{total_count}", *group.index.astype(str)]

    grouped_df = filtered_df.groupby(group_by).apply(format_group)
    # Remove None values (groups with only 1 item)
    grouped_df = grouped_df.dropna()

    # Create chunks ensuring each section stays together
    chunks = []
    current_chunk = []
    current_chunk_size = 0

    for section, symbols in grouped_df.items():
        # Calculate the size of this section (section name + all symbols)
        section_size = len(symbols) + 1  # +1 for the section marker

        # If adding this section would exceed 1000 entries, start a new chunk
        if current_chunk_size + section_size > 1000 and current_chunk:
            chunks.append(current_chunk)
            current_chunk = []
            current_chunk_size = 0

        # Add the section to current chunk
        section_entry = f"###{section},{','.join(symbols)}"
        current_chunk.append(section_entry)
        current_chunk_size += section_size

    # Add the last chunk if it has content
    if current_chunk:
        chunks.append(current_chunk)

    # Return chunks as a list of strings
    return [','.join(chunk) for chunk in chunks]
