import { ActionButton, BrandName, BulletList, Card, Heading } from "@/components/ui";
import { CHANNEL_URL, INSTAGRAM_URL, REVIEWS_URL } from "@/lib/shop";
import { openLink } from "@/lib/telegram";

export function About() {
  return (
    <>
      <header className="flex flex-col items-center px-6 pb-6 pt-8 text-center">
        <img
          src={`${import.meta.env.BASE_URL}logo.jpg`}
          alt=""
          className="mb-4 size-20 rounded-full border border-line object-cover"
        />
        <h1>
          <BrandName className="text-[34px] leading-tight" />
        </h1>
        <p className="mt-2 text-[15px] leading-relaxed text-ink-2">
          Оригинальные вещи · Самая быстрая доставка в любую точку мира
        </p>
      </header>

      <div className="space-y-3 px-4">
        <Card>
          <Heading className="mb-4">Принципы работы</Heading>
          <BulletList
            items={[
              "Все товары — 100% оригинал",
              "Продажи окончательные, обмен и возврат не предусмотрены",
              "Бронирование — только по задатку",
              "Доп. фото и видео — по запросу",
              "Приоритет оперативным покупателям",
              "Примерки возможны в Варшаве",
            ]}
          />
        </Card>

        <Card>
          <Heading className="mb-4">Доставка</Heading>
          <BulletList
            items={[
              "Курьер по Варшаве",
              "Европа и весь мир — транспортной компанией по выбору клиента",
            ]}
          />
        </Card>

        <Card>
          <Heading className="mb-4">Связь</Heading>
          <div className="space-y-3">
            <ActionButton variant="secondary" onClick={() => openLink(CHANNEL_URL)}>
              Telegram канал
            </ActionButton>
            <ActionButton variant="secondary" onClick={() => openLink(REVIEWS_URL)}>
              Отзывы
            </ActionButton>
            <ActionButton variant="secondary" onClick={() => openLink(INSTAGRAM_URL)}>
              Instagram
            </ActionButton>
          </div>
        </Card>
      </div>
    </>
  );
}
