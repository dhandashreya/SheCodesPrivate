program aleo_contract_fixed.aleo {

    // Transition to prove badge based on activity (e.g., message count)
    transition prove_badges(private input: u8) -> bool {
        return input >= 3u8;
    }

    // Transition to verify age privately (e.g., 12 or older)
    transition verify_age(private age: u8) -> bool {
        return age >= 12u8;
    }
}
