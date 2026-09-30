/**
 * "AI image" action for a finished assistant answer.
 *
 * Posts the answer to `generateInfographicImage` and shows the result
 * inline, clearly labelled as AI-generated, with a PNG download link.
 * Failures (including an unconfigured image deployment) surface through
 * the `onError` callback so the caller can toast them.
 */
import { useState } from "react";
import { Button, Spinner } from "@fluentui/react-components";
import { ImageSparkle16Regular } from "@fluentui/react-icons";
import {
  generateInfographicImage,
  imageDataUrl,
  type InfographicImage,
} from "@/api/infographicImage";
import { exportFilename } from "@/api/exportDocument";
import styles from "./MessageList.module.css";

interface InfographicImageActionProps {
  messageId: string;
  markdown: string;
  title: string;
  onError: (error: unknown) => void;
}

export function InfographicImageAction({
  messageId,
  markdown,
  title,
  onError,
}: InfographicImageActionProps) {
  const [pending, setPending] = useState(false);
  const [image, setImage] = useState<InfographicImage | null>(null);

  const generate = () => {
    setPending(true);
    generateInfographicImage(markdown, title)
      .then(setImage)
      .catch(onError)
      .finally(() => {
        setPending(false);
      });
  };

  return (
    <>
      <Button
        size="small"
        appearance="subtle"
        icon={pending ? <Spinner size="extra-tiny" /> : <ImageSparkle16Regular />}
        disabled={pending}
        data-testid={`answer-image-${messageId}`}
        onClick={generate}
      >
        {pending ? "Drawing…" : "AI image"}
      </Button>
      {image !== null && (
        <figure
          className={styles.generatedImage}
          data-testid={`answer-image-result-${messageId}`}
        >
          <img
            src={imageDataUrl(image)}
            alt={`AI-generated infographic: ${title}`}
          />
          <figcaption>
            AI-generated image — verify figures against the cited answer.{" "}
            <a
              href={imageDataUrl(image)}
              download={exportFilename(title, "png")}
            >
              Download PNG
            </a>
          </figcaption>
        </figure>
      )}
    </>
  );
}
