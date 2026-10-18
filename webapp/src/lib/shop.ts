/** Shop contacts, as in the channel and bot/texts.py. */
export const SELLER_USERNAME = "aktavis_eu";
export const CHANNEL_URL = "https://t.me/+cUh6oXRMk3Q4YWNi";
export const REVIEWS_URL = "https://t.me/actavis_feedback";
export const INSTAGRAM_URL = "https://www.instagram.com/aktavis.eu/";

/** Chat with the seller with a message already typed. */
export function sellerLink(text?: string): string {
  const base = `https://t.me/${SELLER_USERNAME}`;
  return text ? `${base}?text=${encodeURIComponent(text)}` : base;
}
