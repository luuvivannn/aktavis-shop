import customOrderBanner from "@/assets/custom_order_banner.jpg";
import { ActionButton, BulletList, Card, Heading, InfoRows, PageHeader } from "@/components/ui";
import { REVIEWS_URL, sellerLink } from "@/lib/shop";
import { haptic, openLink } from "@/lib/telegram";

const MESSAGE = "Привет! Хочу обсудить индивидуальный заказ.";

const DELIVERY: { label: string; time: string | null; price: string }[] = [
  { label: "Карго (Китай)", time: "20–30 дней", price: "10$ / кг" },
  { label: "Авиадоставка", time: "6–9 дней", price: "30$ / кг" },
  { label: "Европа", time: "5–14 дней", price: "5$ / кг" },
  { label: "США", time: null, price: "сроки и цена индивидуально" },
];

/** «Под заказ» tab, laid out like STIIL's: what we do and the button to
 *  the seller first, then what to send, delivery and prepayment. */
export function CustomOrder() {
  return (
    <>
      <PageHeader title="Под заказ" subtitle="Не нашли нужное в каталоге? Найдём и привезём под вас." />
      <div className="space-y-3 px-4">
        <Card className="overflow-hidden p-0">
          <img src={customOrderBanner} alt="" className="w-full" />
          <div className="p-5">
            <Heading>Индивидуальный заказ</Heading>
            <p className="mt-3 text-[15px] leading-relaxed text-ink-2">
              Мы принимаем персональные запросы и готовы оказать помощь в поиске интересующей вас позиции.
            </p>
            <p className="mb-5 mt-3 text-[15px] leading-relaxed text-ink-2">
              Подбор изделий от ведущих мировых брендов осуществляется по стоимости, значительно более выгодной
              по сравнению с бутиками, с полным сопровождением сделки.
            </p>
            <ActionButton
              onClick={() => {
                haptic("medium");
                openLink(sellerLink(MESSAGE));
              }}
            >
              Обсудить заказ
            </ActionButton>
          </div>
        </Card>

        <Card>
          <Heading className="mb-4">Что прислать</Heading>
          <BulletList
            items={[
              "Бренд и модель",
              "Размер",
              "Фото или ссылку на вещь, если есть",
              "Бюджет, на который рассчитываете",
            ]}
          />
        </Card>

        <Card>
          <Heading className="mb-4">Условия доставки</Heading>
          <InfoRows
            rows={DELIVERY.map((d) => ({
              label: d.label,
              value: (
                <>
                  <div>{d.price}</div>
                  {d.time && <div className="mt-0.5 text-[13px] font-normal text-ink-3">{d.time}</div>}
                </>
              ),
            }))}
          />
        </Card>

        <Card className="border-accent-line bg-accent-tint text-[15px] leading-relaxed text-accent-ink">
          <p>
            Индивидуальные заказы принимаются <b>исключительно по 100% предоплате</b>.
          </p>
          <p className="mb-5 mt-2">Рекомендуем заранее ознакомиться с отзывами, подтверждающими нашу репутацию.</p>
          <ActionButton variant="secondary" onClick={() => openLink(REVIEWS_URL)}>
            Отзывы
          </ActionButton>
        </Card>
      </div>
    </>
  );
}
