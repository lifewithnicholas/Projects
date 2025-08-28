import java.util.*;

public class Hangman {
    private static final String[] WORDS = {
        "java", "computer", "hangman", "programming", "application", "developer"
    };
    private static final int MAX_ATTEMPTS = 6;

    public static void main(String[] args) {
        Random rand = new Random();
        String wordToGuess = WORDS[rand.nextInt(WORDS.length)];
        char[] guessedWord = new char[wordToGuess.length()];
        Arrays.fill(guessedWord, '_');

        Set<Character> guessedLetters = new HashSet<>();
        int attemptsLeft = MAX_ATTEMPTS;

        Scanner scanner = new Scanner(System.in);

        System.out.println("=== Welcome to Hangman ===");

        while (attemptsLeft > 0) {
            System.out.println("\nWord: " + String.valueOf(guessedWord));
            System.out.println("Attempts left: " + attemptsLeft);
            System.out.print("Guess a letter: ");
            String input = scanner.nextLine().toLowerCase();

            if (input.length() != 1 || !Character.isLetter(input.charAt(0))) {
                System.out.println("⚠ Please enter a single valid letter.");
                continue;
            }

            char guess = input.charAt(0);

            if (guessedLetters.contains(guess)) {
                System.out.println("⚠ You already guessed that letter!");
                continue;
            }

            guessedLetters.add(guess);

            if (wordToGuess.indexOf(guess) >= 0) {
                // Correct guess
                for (int i = 0; i < wordToGuess.length(); i++) {
                    if (wordToGuess.charAt(i) == guess) {
                        guessedWord[i] = guess;
                    }
                }
                if (String.valueOf(guessedWord).equals(wordToGuess)) {
                    System.out.println("\n🎉 You win! The word was: " + wordToGuess);
                    return;
                }
            } else {
                // Wrong guess
                attemptsLeft--;
                System.out.println("❌ Wrong guess!");
            }
        }

        System.out.println("\n💀 Game over! The word was: " + wordToGuess);
    }
}
